import json
import unittest
from pathlib import Path

from alfa_document_intelligence.ocr_adapter import OCRPageResult, OCRToken
from alfa_document_intelligence.contracts import validate_document_record
from alfa_document_intelligence.document_validation import validate_document_consistency
from alfa_document_intelligence.semantic_proposals import (
    SemanticProposalError,
    propose_common_fields,
)

SOURCE = "a" * 64
POLYGON = ((0.1, 0.2), (0.8, 0.2), (0.8, 0.4), (0.1, 0.4))


def page(number, tokens, source=SOURCE):
    return OCRPageResult(source, number, "synthetic-ocr", "test-1", "it+en", tuple(tokens))


class SemanticProposalTests(unittest.TestCase):
    def test_proposals_remain_uncertain_and_bind_every_alternative_to_ocr_evidence(self):
        tokens = [
            OCRToken("t-date", "Data: 01/02/2026", POLYGON),
            OCRToken("t-amount", "Totale € 1.234,56", POLYGON),
            OCRToken("t-currency", "EUR", POLYGON),
        ]
        result = propose_common_fields([page(1, tokens)])
        self.assertEqual(result["date_candidates"]["status"], "uncertain")
        self.assertIsNone(result["date_candidates"]["value"])
        self.assertEqual(
            {item["value"] for item in result["date_candidates"]["alternatives"]},
            {"2026-02-01", "2026-01-02"},
        )
        amount = result["amount_candidates"]
        self.assertEqual(amount["status"], "uncertain")
        self.assertEqual(amount["alternatives"][0]["value"], "1234.56")
        total = result["total_amount"]
        self.assertEqual(total["status"], "uncertain")
        self.assertEqual(total["alternatives"][0]["value"], "1234.56")
        self.assertEqual(total["alternatives"][0]["evidence"][0]["literal"], "Totale € 1.234,56")
        for field in result.values():
            for ref in field["evidence"]:
                self.assertEqual(ref["source_sha256"], SOURCE)
                self.assertEqual(ref["page_number"], 1)
                self.assertEqual(ref["producer"]["stage"], "ocr")
                self.assertTrue(ref["token_ids"])

    def test_output_satisfies_document_evidence_invariants(self):
        fixture = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
        record = json.loads(fixture.read_text(encoding="utf-8"))
        proposals = propose_common_fields([
            page(1, [OCRToken("t1", "01/02/2026 EUR 123,45", POLYGON)])
        ])
        record["fields"].update(proposals)
        self.assertEqual(validate_document_record(record), [])

    def test_does_not_infer_eur_from_project_scope_or_ambiguous_dollar_symbol(self):
        result = propose_common_fields([
            page(1, [OCRToken("t-amount", "12.50 $", POLYGON)])
        ])
        self.assertIn("amount_candidates", result)
        self.assertNotIn("total_amount", result)
        self.assertNotIn("currency", result)

    def test_preserves_explicit_non_eur_iso_currency_as_uncertain_evidence(self):
        result = propose_common_fields([
            page(1, [OCRToken("t-currency", "USD", POLYGON)])
        ])

        currency = result["currency"]
        self.assertEqual(currency["status"], "uncertain")
        self.assertIsNone(currency["value"])
        self.assertEqual(
            [item["value"] for item in currency["alternatives"]],
            ["USD"],
        )
        self.assertEqual(currency["alternatives"][0]["evidence"][0]["literal"], "USD")
        self.assertNotIn("EUR", [item["value"] for item in currency["alternatives"]])

    def test_does_not_call_a_single_date_or_amount_confirmed(self):
        result = propose_common_fields([
            page(1, [OCRToken("t1", "2026-10-14 12,50", POLYGON)])
        ])
        self.assertTrue(all(value["status"] == "uncertain" for value in result.values()))
        self.assertIn("date_candidates", result)
        self.assertNotIn("issue_date", result)
        self.assertIn("amount_candidates", result)
        self.assertNotIn("total_amount", result)

    def test_ignores_invalid_dates_and_unrecognized_amounts_without_inventing_values(self):
        result = propose_common_fields([
            page(1, [OCRToken("t1", "31/02/2026 ref 1234", POLYGON)])
        ])
        self.assertEqual(result, {})

    def test_requires_one_source_and_unique_pages_and_tokens(self):
        token = OCRToken("t1", "12,50", POLYGON)
        with self.assertRaisesRegex(SemanticProposalError, "same source"):
            propose_common_fields([page(1, [token]), page(2, [token], "b" * 64)])
        with self.assertRaisesRegex(SemanticProposalError, "unique"):
            propose_common_fields([page(1, [token]), page(1, [token])])
        with self.assertRaisesRegex(SemanticProposalError, "unique OCRToken"):
            propose_common_fields([page(1, [token, token])])

    def test_requires_valid_source_hash_and_pages(self):
        with self.assertRaisesRegex(SemanticProposalError, "source_sha256"):
            propose_common_fields([page(1, [], "invalid")])
        with self.assertRaisesRegex(SemanticProposalError, "at least one"):
            propose_common_fields([])

    def test_rejects_malformed_token_evidence_before_emitting_candidates(self):
        bad_polygon = OCRToken("bad", "12,50", ((0.1, 0.2), (1.1, 0.2), (0.8, 0.4)))
        with self.assertRaisesRegex(SemanticProposalError, "normalized"):
            propose_common_fields([page(1, [bad_polygon])])
        empty_text = OCRToken("empty", " ", POLYGON)
        with self.assertRaisesRegex(SemanticProposalError, "non-empty"):
            propose_common_fields([page(1, [empty_text])])

    def test_ambiguous_amount_formats_are_normalized_from_the_last_separator(self):
        values = propose_common_fields([
            page(1, [
                OCRToken("it", "1.234,56", POLYGON),
                OCRToken("en", "1,234.56", POLYGON),
            ])
        ])["amount_candidates"]["alternatives"]
        self.assertEqual([item["value"] for item in values], ["1234.56", "1234.56"])
        self.assertEqual(values[0]["normalization"]["original_literal"], "1.234,56")
        self.assertEqual(values[1]["normalization"]["original_literal"], "1,234.56")


    def test_total_candidates_require_an_explicit_italian_or_english_label(self):
        result = propose_common_fields([page(1, [
            OCRToken("subtotal", "Subtotale € 100,00", POLYGON),
            OCRToken("vat", "IVA 22,00", POLYGON),
            OCRToken("total-it", "Importo totale da pagare: EUR 122,00", POLYGON),
            OCRToken("total-en", "Grand total: £ 122.00", POLYGON),
        ])])
        self.assertEqual(
            [item["value"] for item in result["total_amount"]["alternatives"]],
            ["122.00", "122.00"],
        )
        self.assertEqual(
            [item["evidence"][0]["literal"] for item in result["total_amount"]["alternatives"]],
            ["Importo totale da pagare: EUR 122,00", "Grand total: £ 122.00"],
        )
        self.assertEqual(
            [item["value"] for item in result["amount_candidates"]["alternatives"]],
            ["100.00", "22.00", "122.00", "122.00"],
        )
        self.assertEqual(result["total_amount"]["status"], "uncertain")

    def test_explicit_date_roles_remain_uncertain_and_feed_hotel_validation(self):
        invoice_dates = propose_common_fields([page(1, [
            OCRToken("issue-date", "Data di emissione: 01/02/2026", POLYGON),
        ])])
        self.assertEqual(invoice_dates["issue_date"]["status"], "uncertain")
        self.assertEqual(
            invoice_dates["issue_date"]["alternatives"][0]["evidence"][0]["literal"],
            "Data di emissione: 01/02/2026",
        )

        fixture = Path(__file__).parent / "fixtures" / "synthetic_hotel_document.json"
        record = json.loads(fixture.read_text(encoding="utf-8"))
        source_hash = record["source"]["sha256"]
        hotel_dates = propose_common_fields([page(1, [
            OCRToken("check-in", "Check-in: 12/10/2026", POLYGON),
            OCRToken("check-out", "Check-out: 14/10/2026", POLYGON),
        ], source_hash)])
        self.assertEqual(hotel_dates["check_in_date"]["status"], "uncertain")
        self.assertEqual(hotel_dates["check_out_date"]["status"], "uncertain")
        record["fields"].update(hotel_dates)
        self.assertEqual(validate_document_record(record), [])
        findings = validate_document_consistency(record)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["outcome"], "indeterminate")
        self.assertEqual(
            {item["literal"] for item in findings[0]["evidence"]},
            {"Check-in: 12/10/2026", "Check-out: 14/10/2026"},
        )




    def test_payment_role_cues_must_start_the_ocr_token(self):
        result = propose_common_fields([page(1, [
            OCRToken("tip-prefix", "Nota: Mancia: 2,00", POLYGON),
            OCRToken("paid-prefix", "Descrizione: Importo pagato: 4,00", POLYGON),
            OCRToken("method-prefix", "Dettaglio: Metodo di pagamento: carta", POLYGON),
        ])])
        self.assertNotIn("tip_amount", result)
        self.assertNotIn("payment_amount", result)
        self.assertNotIn("payment_method", result)

    def test_tip_amount_requires_explicit_same_token_label_and_stays_distinct(self):
        result = propose_common_fields([page(1, [
            OCRToken("tip-it", "Mancia: 2,50", POLYGON),
            OCRToken("tip-en", "Gratuity £ 2.50", POLYGON),
            OCRToken("paid", "Importo pagato: 12,00", POLYGON),
            OCRToken("total", "Totale: 14,50", POLYGON),
            OCRToken("unlabeled", "3,00", POLYGON),
            OCRToken("due", "Tip amount due: 3.00", POLYGON),
        ])])
        self.assertEqual([x["value"] for x in result["tip_amount"]["alternatives"]], ["2.50", "2.50"])
        self.assertEqual(
            [x["evidence"][0]["literal"] for x in result["tip_amount"]["alternatives"]],
            ["Mancia: 2,50", "Gratuity £ 2.50"],
        )
        self.assertEqual([x["value"] for x in result["payment_amount"]["alternatives"]], ["12.00"])
        self.assertEqual([x["value"] for x in result["total_amount"]["alternatives"]], ["14.50", "3.00"])
        self.assertEqual(result["tip_amount"]["status"], "uncertain")


    def test_payment_reference_requires_explicit_role_and_stays_uncertain(self):
        result = propose_common_fields([page(1, [
            OCRToken("it", "Rif. transazione: TX-2026/004", POLYGON),
            OCRToken("en", "Payment reference: ABC_123", POLYGON),
            OCRToken("auth", "Authorization code 123456", POLYGON),
            OCRToken("auth-it", "Autorizzazione: 123456", POLYGON),
            OCRToken("generic", "Reference: ABC_123", POLYGON),
            OCRToken("invoice", "Invoice number: ABC_123", POLYGON),
        ])])
        candidate = result["payment_reference"]
        self.assertEqual(candidate["status"], "uncertain")
        self.assertIsNone(candidate["value"])
        self.assertEqual([x["value"] for x in candidate["alternatives"]], ["TX-2026/004", "ABC_123"])
        self.assertEqual(
            [x["evidence"][0]["literal"] for x in candidate["alternatives"]],
            ["Rif. transazione: TX-2026/004", "Payment reference: ABC_123"],
        )
        self.assertTrue(all(x["evidence"][0]["source_sha256"] == SOURCE for x in candidate["alternatives"]))

    def test_paid_amount_and_payment_method_require_explicit_same_token_cues(self):
        result = propose_common_fields([page(1, [
            OCRToken("total", "Totale: EUR 18,00", POLYGON),
            OCRToken("due", "Amount due: 18.00", POLYGON),
            OCRToken("paid-it", "Importo pagato: 12,00", POLYGON),
            OCRToken("paid-en", "Amount paid £ 12.00", POLYGON),
            OCRToken("method-it", "Metodo di pagamento: carta di credito", POLYGON),
            OCRToken("method-en", "Payment method: bank transfer", POLYGON),
            OCRToken("generic-method", "Pagamento carta", POLYGON),
            OCRToken("auth", "Authorization code 123456", POLYGON),
            OCRToken("paid-to", "Pagato a Rossi", POLYGON),
        ])])
        self.assertEqual([x["value"] for x in result["payment_amount"]["alternatives"]], ["12.00", "12.00"])
        self.assertEqual([x["value"] for x in result["total_amount"]["alternatives"]], ["18.00", "18.00"])
        self.assertEqual([x["value"] for x in result["payment_method"]["alternatives"]], ["card", "bank_transfer"])
        self.assertTrue(all(result[name]["status"] == "uncertain" for name in ("payment_amount", "payment_method")))
        self.assertEqual(
            result["payment_amount"]["alternatives"][0]["evidence"][0]["literal"],
            "Importo pagato: 12,00",
        )
        self.assertNotIn("Totale: EUR 18,00", [x["evidence"][0]["literal"] for x in result["payment_amount"]["alternatives"]])

    def test_payment_cues_do_not_infer_method_from_pos_or_authorization_text(self):
        result = propose_common_fields([page(1, [
            OCRToken("pos", "PAGAMENTO CARTA", POLYGON),
            OCRToken("auth", "Autorizzazione 123456", POLYGON),
            OCRToken("card-auth", "Card authorization", POLYGON),
            OCRToken("payment", "Pagamento: 12,00", POLYGON),
            OCRToken("due", "Da pagare: 12,00", POLYGON),
        ])])
        self.assertNotIn("payment_method", result)
        self.assertNotIn("payment_amount", result)
        self.assertIn("amount_candidates", result)

    def test_tax_roles_require_explicit_same_token_labels_and_keep_uncertain_evidence(self):
        result = propose_common_fields([page(1, [
            OCRToken('base-it', 'Imponibile: 100,00', POLYGON),
            OCRToken('vat-it', 'IVA 22% 22,00', POLYGON),
            OCRToken('rate-it', 'Aliquota IVA: 22%', POLYGON),
            OCRToken('base-en', 'Taxable base: 100.00', POLYGON),
            OCRToken('base-it-currency', 'Imponibile EUR 100,00', POLYGON),
            OCRToken('base-en-currency', 'Taxable base EUR 50.00', POLYGON),
            OCRToken('vat-en', 'VAT amount: 22.00', POLYGON),
            OCRToken('vat-en-currency', 'VAT amount EUR 5.00', POLYGON),
            OCRToken('rate-en', 'VAT rate: 22%', POLYGON),
        ])])
        self.assertEqual([x['value'] for x in result['taxable_base']['alternatives']], ['100.00', '100.00', '100.00', '50.00'])
        self.assertEqual([x['value'] for x in result['vat_amount']['alternatives']], ['22.00', '22.00', '5.00'])
        self.assertEqual([x['value'] for x in result['vat_rate']['alternatives']], ['22', '22', '22'])
        self.assertTrue(all(result[name]['status'] == 'uncertain' for name in ('taxable_base', 'vat_amount', 'vat_rate')))
        self.assertEqual(result['vat_amount']['alternatives'][0]['evidence'][0]['literal'], 'IVA 22% 22,00')
        self.assertIn('Aliquota IVA: 22%', [x['evidence'][0]['literal'] for x in result['vat_rate']['alternatives']])

    def test_tax_role_candidates_are_not_inferred_without_explicit_labels(self):
        result = propose_common_fields([page(1, [
            OCRToken('numbers', '100,00 22,00 22%', POLYGON),
            OCRToken('non-role', 'Totale: 122,00', POLYGON),
        ])])
        self.assertNotIn('taxable_base', result)
        self.assertNotIn('vat_amount', result)
        self.assertNotIn('vat_rate', result)
        self.assertIn('total_amount', result)
    def test_merchant_and_supplier_candidates_require_explicit_role_labels(self):
        result = propose_common_fields([page(1, [
            OCRToken("merchant-it", "Esercente: Hotel Aurora S.r.l.", POLYGON),
            OCRToken("supplier-it", "Fornitore: Cafe Roma", POLYGON),
            OCRToken("merchant-en", "Merchant: Acme Ltd", POLYGON),
            OCRToken("supplier-en", "Supplier: Alpha Inc", POLYGON),
            OCRToken("customer", "Cliente: EsercenteDemo S.p.A.", POLYGON),
        ])])
        self.assertEqual([x["value"] for x in result["merchant_name"]["alternatives"]], ["Hotel Aurora S.r.l.", "Acme Ltd"])
        self.assertEqual([x["value"] for x in result["supplier_name"]["alternatives"]], ["Cafe Roma", "Alpha Inc"])
        self.assertEqual(result["merchant_name"]["status"], "uncertain")
        self.assertEqual(result["merchant_name"]["alternatives"][0]["evidence"][0]["literal"], "Esercente: Hotel Aurora S.r.l.")
        self.assertNotIn("Cliente: EsercenteDemo S.p.A.", [x["evidence"][0]["literal"] for x in result["merchant_name"]["alternatives"]])


    def test_bill_to_and_sold_to_remain_distinct_and_require_explicit_cues(self):
        result = propose_common_fields([page(1, [
            OCRToken("bill-to", "Bill to: Alpha S.r.l.", POLYGON),
            OCRToken("sold-to", "Sold to: Beta GmbH", POLYGON),
            OCRToken("client-it", "Cliente: Gamma S.p.A.", POLYGON),
            OCRToken("customer-en", "Customer: Delta Ltd", POLYGON),
            OCRToken("recipient", "Destinatario: Epsilon S.p.A.", POLYGON),
            OCRToken("payment-recipient", "Payment recipient: Zeta Ltd", POLYGON),
            OCRToken("unlabeled", "Eta Ltd", POLYGON),
            OCRToken("split-label", "Bill to:", POLYGON),
            OCRToken("split-value", "Theta Inc", POLYGON),
            OCRToken("prefix-noise", "Payment recipient: Zeta Bill to: Iota Ltd", POLYGON),
            OCRToken("both-cues-bill-first", "Bill to: Kappa Ltd Sold to: Lambda GmbH", POLYGON),
            OCRToken("both-cues-sold-first", "Sold to: Mu GmbH Bill to: Nu S.r.l.", POLYGON),
            OCRToken("trailing-field-noise", "Bill to: Xi Ltd Invoice Date: 14/10/2026", POLYGON),
            OCRToken("trailing-address", "Bill to: Omicron Ltd Address: 1 Main Street", POLYGON),
            OCRToken("trailing-ship-to", "Bill to: Pi Ltd Ship to: Warehouse 4", POLYGON),
            OCRToken("trailing-tax-id", "Bill to: Rho Ltd Tax ID: 123456", POLYGON),
            OCRToken("trailing-amount-due", "Bill to: Sigma Ltd Amount due: 12.00", POLYGON),
        ])])
        bill_to = result["bill_to_name"]
        sold_to = result["sold_to_name"]
        self.assertEqual(bill_to["status"], "uncertain")
        self.assertEqual(sold_to["status"], "uncertain")
        self.assertIsNone(bill_to["value"])
        self.assertIsNone(sold_to["value"])
        self.assertEqual([x["value"] for x in bill_to["alternatives"]], ["Alpha S.r.l."])
        self.assertEqual([x["value"] for x in sold_to["alternatives"]], ["Beta GmbH"])
        self.assertEqual(
            bill_to["alternatives"][0]["evidence"][0]["literal"],
            "Bill to: Alpha S.r.l.",
        )
        self.assertEqual(
            sold_to["alternatives"][0]["evidence"][0]["literal"],
            "Sold to: Beta GmbH",
        )
        for candidate, expected_token in ((bill_to, "bill-to"), (sold_to, "sold-to")):
            evidence = candidate["alternatives"][0]["evidence"][0]
            self.assertEqual(evidence["source_sha256"], SOURCE)
            self.assertEqual(evidence["page_number"], 1)
            self.assertEqual(evidence["token_ids"], [expected_token])
        self.assertNotIn("customer_name", result)
        self.assertNotIn("merchant_name", result)
        self.assertNotIn("supplier_name", result)
        fixture = Path(__file__).parent / "fixtures" / "synthetic_invoice.json"
        record = json.loads(fixture.read_text(encoding="utf-8"))
        record["fields"].update(result)
        self.assertEqual(validate_document_record(record), [])

    def test_empty_entity_label_or_unlabeled_text_never_creates_a_name(self):
        result = propose_common_fields([page(1, [
            OCRToken("blank", "Fornitore:", POLYGON),
            OCRToken("free-text", "Acme Ltd", POLYGON),
            OCRToken("customer", "Cliente: Beta S.p.A.", POLYGON),
        ])])
        self.assertNotIn("merchant_name", result)
        self.assertNotIn("supplier_name", result)

    def test_document_number_requires_an_explicit_label_and_preserves_source_literal(self):
        result = propose_common_fields([page(1, [
            OCRToken("number-it", "Numero fattura: 2026/001", POLYGON),
            OCRToken("number-en", "Invoice No. A-19", POLYGON),
            OCRToken("number-short", "N° documento 0042", POLYGON),
            OCRToken("unlabeled", "2026/001", POLYGON),
            OCRToken("customer-id", "Cliente: 2026/001", POLYGON),
            OCRToken("empty", "Invoice number:", POLYGON),
        ])])
        candidate = result["document_number"]
        self.assertEqual(candidate["status"], "uncertain")
        self.assertIsNone(candidate["value"])
        self.assertEqual(
            [item["value"] for item in candidate["alternatives"]],
            ["2026/001", "A-19", "0042"],
        )
        self.assertEqual(
            [item["evidence"][0]["literal"] for item in candidate["alternatives"]],
            ["Numero fattura: 2026/001", "Invoice No. A-19", "N° documento 0042"],
        )
        self.assertTrue(all(
            item["evidence"][0]["source_sha256"] == SOURCE
            and item["evidence"][0]["page_number"] == 1
            and item["evidence"][0]["token_ids"]
            for item in candidate["alternatives"]
        ))

    def test_document_number_requires_single_token_label_and_value(self):
        result = propose_common_fields([page(1, [
            OCRToken("trailing", "Invoice number A-19 date 14/10/2026", POLYGON),
            OCRToken("partial-label", "Invoice number:", POLYGON),
            OCRToken("split-label", "Invoice number", POLYGON),
            OCRToken("split-value", "A-19", POLYGON),
        ])])
        self.assertNotIn("document_number", result)

    def test_vat_registration_number_requires_explicit_type_label_and_eleven_digits(self):
        result = propose_common_fields([page(1, [
            OCRToken("partita-iva", "Partita IVA: 01234567891", POLYGON),
            OCRToken("p-iva", "P.IVA IT 123 456 78901", POLYGON),
            OCRToken("vat-number", "VAT No. 12345678901", POLYGON),
            OCRToken("vat-amount", "VAT 22% 22.00", POLYGON),
            OCRToken("tax-code", "Codice fiscale: 01234567891", POLYGON),
            OCRToken("tax-id", "Tax ID: 01234567891", POLYGON),
            OCRToken("unlabeled", "01234567891", POLYGON),
            OCRToken("short", "P.IVA: 1234567890", POLYGON),
            OCRToken("long", "VAT ID: 123456789012", POLYGON),
        ])])
        candidate = result["vat_registration_number"]
        self.assertEqual(candidate["status"], "uncertain")
        self.assertIsNone(candidate["value"])
        self.assertEqual(
            [item["value"] for item in candidate["alternatives"]],
            ["01234567891", "IT 123 456 78901", "12345678901"],
        )
        self.assertEqual(
            [item["evidence"][0]["literal"] for item in candidate["alternatives"]],
            ["Partita IVA: 01234567891", "P.IVA IT 123 456 78901", "VAT No. 12345678901"],
        )
        self.assertTrue(all(
            item["evidence"][0]["source_sha256"] == SOURCE
            and item["evidence"][0]["page_number"] == 1
            and item["evidence"][0]["token_ids"]
            for item in candidate["alternatives"]
        ))

    def test_vat_registration_number_is_not_checksum_or_fiscal_validity_evidence(self):
        result = propose_common_fields([page(1, [
            OCRToken("possibly-invalid", "Partita IVA: 12345678901", POLYGON),
        ])])
        candidate = result["vat_registration_number"]
        self.assertEqual(candidate["status"], "uncertain")
        self.assertEqual(candidate["alternatives"][0]["value"], "12345678901")
        self.assertEqual(
            candidate["alternatives"][0]["normalization"]["rule_id"],
            "explicit-vat-registration-label-preserve-literal",
        )

    def test_document_family_candidates_require_explicit_title_cues_and_remain_uncertain(self):
        result = propose_common_fields([page(1, [
            OCRToken("invoice-it", "FATTURA", POLYGON),
            OCRToken("fiscal-it", "RICEVUTA FISCALE", POLYGON),
            OCRToken("parking-it", "RICEVUTA PARCHEGGIO", POLYGON),
            OCRToken("hotel-en", "HOTEL INVOICE", POLYGON),
            OCRToken("pos-en", "CARD PAYMENT SLIP", POLYGON),
            OCRToken("generic", "RECEIPT", POLYGON),
            OCRToken("unlabeled", "HOTEL AURORA", POLYGON),
        ])])
        candidate = result["document_family_candidates"]
        self.assertEqual(candidate["status"], "uncertain")
        self.assertIsNone(candidate["value"])
        self.assertEqual(
            [item["value"] for item in candidate["alternatives"]],
            ["invoice", "fiscal_receipt", "parking_receipt", "hotel_document", "pos_slip"],
        )
        self.assertEqual(
            [item["evidence"][0]["literal"] for item in candidate["alternatives"]],
            ["FATTURA", "RICEVUTA FISCALE", "RICEVUTA PARCHEGGIO", "HOTEL INVOICE", "CARD PAYMENT SLIP"],
        )
        self.assertTrue(all(
            item["evidence"][0]["source_sha256"] == SOURCE
            and item["evidence"][0]["page_number"] == 1
            and item["evidence"][0]["token_ids"]
            for item in candidate["alternatives"]
        ))

    def test_pos_family_cue_does_not_classify_fiscal_document_state(self):
        result = propose_common_fields([page(1, [
            OCRToken("pos", "POS RECEIPT", POLYGON),
        ])])
        self.assertEqual(set(result), {"document_family_candidates"})
        self.assertEqual(
            [item["value"] for item in result["document_family_candidates"]["alternatives"]],
            ["pos_slip"],
        )

    def test_expense_report_context_requires_explicit_same_token_labels_and_stays_uncertain(self):
        tokens = [OCRToken("traveler", "Nome trasfertista: Ada Rossi", POLYGON), OCRToken("destination", "Destinazione trasferta: Milano", POLYGON), OCRToken("purpose", "Causale trasferta: incontro cliente", POLYGON), OCRToken("start", "Inizio trasferta: 01/02/2026", POLYGON), OCRToken("end", "Fine trasferta: 03/02/2026", POLYGON)]
        result = propose_common_fields([page(1, tokens)], document_family="expense_report")
        for name in ("traveler_name", "trip_destination", "trip_purpose", "trip_start_date", "trip_end_date"):
            self.assertEqual(result[name]["status"], "uncertain")
            self.assertIsNone(result[name]["value"])
            self.assertTrue(result[name]["alternatives"])
            for alt in result[name]["alternatives"]:
                evidence = alt["evidence"][0]
                self.assertEqual(evidence["source_sha256"], SOURCE)
                self.assertEqual(evidence["page_number"], 1)
                self.assertTrue(evidence["token_ids"])
                self.assertIn(evidence["literal"], [token.text for token in tokens])


    def test_expense_report_context_supports_explicit_english_labels(self):
        tokens = [
            OCRToken("traveler-en", "Employee name: Alex Morgan", POLYGON),
            OCRToken("destination-en", "Trip destination: London", POLYGON),
            OCRToken("purpose-en", "Business purpose: supplier meeting", POLYGON),
            OCRToken("start-en", "Trip start date: 2026-10-14", POLYGON),
            OCRToken("end-en", "Trip end date: 2026-10-16", POLYGON),
        ]
        result = propose_common_fields([page(1, tokens)], document_family="expense_report")
        expected = {
            "traveler_name": "Alex Morgan",
            "trip_destination": "London",
            "trip_purpose": "supplier meeting",
            "trip_start_date": "2026-10-14",
            "trip_end_date": "2026-10-16",
        }
        for field_name, expected_value in expected.items():
            candidate = result[field_name]
            self.assertEqual(candidate["status"], "uncertain")
            self.assertIsNone(candidate["value"])
            self.assertEqual(candidate["alternatives"][0]["value"], expected_value)
            self.assertEqual(candidate["evidence"][0]["literal"], next(
                token.text for token in tokens
                if token.token_id == candidate["evidence"][0]["token_ids"][0]
            ))

    def test_expense_context_ignores_unlabeled_values_and_non_expense_families(self):
        tokens = [OCRToken("name", "Ada Rossi", POLYGON), OCRToken("city", "Milano", POLYGON), OCRToken("purpose", "Incontro cliente", POLYGON), OCRToken("date", "01/02/2026", POLYGON)]
        expense = propose_common_fields([page(1, tokens)], document_family="expense_report")
        for name in ("traveler_name", "trip_destination", "trip_purpose", "trip_start_date", "trip_end_date"):
            self.assertNotIn(name, expense)
        invoice = propose_common_fields([page(1, [OCRToken("labeled", "Nome trasfertista: Ada Rossi", POLYGON), OCRToken("date", "Inizio trasferta: 01/02/2026", POLYGON)])], document_family="invoice")
        self.assertNotIn("traveler_name", invoice)
        self.assertNotIn("trip_start_date", invoice)


from unittest.mock import patch

class OverflowDiagnosticTests(unittest.TestCase):
    def test_accumulation_stops_at_first_overflow_and_preserves_limit_order(self):
        from alfa_document_intelligence import semantic_proposals as module
        tokens = [OCRToken(str(i), f"{i + 1},50", POLYGON) for i in range(102)]
        result = propose_common_fields([page(1, tokens[:100])])
        self.assertEqual(
            [item["value"] for item in result["amount_candidates"]["alternatives"]],
            [f"{i + 1}.50" for i in range(100)],
        )
        original = module._evidence
        with patch.object(module, "_evidence", wraps=original) as evidence:
            with self.assertRaises(SemanticProposalError) as caught:
                propose_common_fields([page(1, tokens)])
        self.assertEqual(caught.exception.code, "semantic_proposal_field_limit")
        self.assertLessEqual(evidence.call_count, 101)

    def test_per_field_overflow_has_stable_code(self):
        tokens = [OCRToken(str(i), '12,50', POLYGON) for i in range(101)]
        with self.assertRaises(SemanticProposalError) as caught:
            propose_common_fields([page(1, tokens)])
        self.assertEqual(caught.exception.code, 'semantic_proposal_field_limit')

    def test_catalog_overflow_has_stable_code(self):
        from test_document_family_catalog import catalog_payload
        from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog
        catalog = load_custom_family_catalog(json.dumps(catalog_payload()))
        tokens = [OCRToken(str(i), 'RICEVUTA TAXI', POLYGON) for i in range(101)]
        with self.assertRaises(SemanticProposalError) as caught:
            propose_common_fields([page(1, tokens)], custom_family_catalog=catalog)
        self.assertEqual(caught.exception.code, 'semantic_proposal_catalog_limit')

    def test_family_merge_overflow_has_stable_code(self):
        from test_document_family_catalog import catalog_payload
        from alfa_document_intelligence.document_family_catalog import load_custom_family_catalog
        catalog = load_custom_family_catalog(json.dumps(catalog_payload()))
        tokens = [OCRToken('built'+str(i), 'INVOICE', POLYGON) for i in range(51)]
        tokens += [OCRToken('custom'+str(i), 'RICEVUTA TAXI', POLYGON) for i in range(50)]
        with self.assertRaises(SemanticProposalError) as caught:
            propose_common_fields([page(1, tokens)], custom_family_catalog=catalog)
        self.assertEqual(caught.exception.code, 'semantic_proposal_family_limit')
    def test_invalid_input_is_not_overflow(self):
        with self.assertRaises(SemanticProposalError) as caught:
            propose_common_fields([page(1, []), page(1, [])])
        self.assertFalse(hasattr(caught.exception, 'code'))


if __name__ == "__main__":
    unittest.main()
