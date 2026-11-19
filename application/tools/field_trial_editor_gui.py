"""Manual local reference editor. Opens no network connections and runs no OCR."""
from __future__ import annotations

import argparse
import io
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from tools.field_trial_editor import (
    EDITABLE, add_manual_match, add_reference_documents, edit_reference,
    load_matching_drafts, remove_reference_document, save_matching_drafts,
    save_reference_draft, serialize_reference,
)
from tools.field_trial_local_files import _read_sheet, open_local_file
from tools.field_trial_sheet import SHEET, _rows_from_bytes

_MAX_INPUT = 25 * 1024 * 1024
_MAX_PIXELS = 20_000_000
_LABELS = {
    'ruolo': 'Ruolo', 'lingua': 'Lingua', 'total_amount': 'Totale (es. 12.34)',
    'issue_date': 'Data (AAAA-MM-GG)', 'currency': 'Valuta (es. EUR)',
    'document_number': 'Numero documento', 'vat_registration_number': 'Partita IVA',
    'merchant_name': 'Esercente', 'esclusioni_motivo': 'Dati assenti o illeggibili',
}


def _preview(root, path, page_number):
    """Read one authorized file through a guarded handle and render locally."""
    with open_local_file(root, path) as stream:
        data = stream.read(_MAX_INPUT + 1)
    if not data or len(data) > _MAX_INPUT:
        raise ValueError('invalid input')
    suffix = Path(path).suffix.lower()
    if suffix == '.pdf':
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            total = len(pdf)
            if not 1 <= total <= 100 or not 0 <= page_number < total:
                raise ValueError('invalid page')
            page = pdf[page_number]
            try:
                width, height = page.get_size()
                if width <= 0 or height <= 0 or width > 10000 or height > 10000 or width * height > _MAX_PIXELS:
                    raise ValueError('page too large')
                image = page.render(scale=1).to_pil().convert('RGB')
            finally:
                page.close()
        finally:
            pdf.close()
    else:
        if suffix not in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.gif', '.bmp'}:
            raise ValueError('unsupported format')
        Image.MAX_IMAGE_PIXELS = _MAX_PIXELS
        source = Image.open(io.BytesIO(data))
        try:
            total = min(getattr(source, 'n_frames', 1), 100)
            if not 0 <= page_number < total:
                raise ValueError('invalid page')
            source.seek(page_number)
            if source.width * source.height > _MAX_PIXELS:
                raise ValueError('image too large')
            image = source.convert('RGB')
        finally:
            source.close()
    image.thumbnail((680, 720))
    return image, total


def run(private_root, sheet_path, authorised_root):
    with open_local_file(private_root, sheet_path) as stream:
        rows = _rows_from_bytes(_read_sheet(stream), SHEET)
    if not rows or len(rows) > 50:
        raise ValueError('invalid reference')
    window = tk.Tk()
    window.title('OCR2 — Preparazione manuale del campione')
    window.geometry('1180x780')
    window.minsize(900, 650)
    left = ttk.Frame(window, padding=12); left.pack(side='left', fill='y')
    right = ttk.Frame(window, padding=12); right.pack(side='left', expand=True, fill='both')
    status = tk.StringVar(); page_label = tk.StringVar()
    ttk.Label(left, textvariable=status, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
    ttk.Label(left, text='Leggi il documento e inserisci solo i valori visibili.\nNessun OCR viene avviato.', wraplength=400).pack(anchor='w', pady=(4, 10))
    entries = {}
    for name in EDITABLE:
        ttk.Label(left, text=_LABELS[name]).pack(anchor='w')
        value = tk.StringVar(); entries[name] = value
        if name in ('ruolo', 'lingua'):
            choices = ('', 'nota', 'giustificativo') if name == 'ruolo' else ('', 'it', 'en')
            widget = ttk.Combobox(left, textvariable=value, values=choices, state='readonly', width=38)
        else:
            widget = ttk.Entry(left, textvariable=value, width=41)
        widget.pack(anchor='w', pady=(0, 4))
    image_label = ttk.Label(right, anchor='center'); image_label.pack(expand=True, fill='both')
    page_controls = ttk.Frame(right); page_controls.pack(fill='x')
    ttk.Label(page_controls, textvariable=page_label).pack(side='left')
    state = {'index': 0, 'page': 0, 'total': 1, 'rows': rows, 'image': None,
             'last_saved': serialize_reference(rows), 'matches': [], 'matches_saved': []}

    def preview():
        try:
            image, total = _preview(authorised_root, state['rows'][state['index']]['percorso_locale'], state['page'])
            state['image'] = ImageTk.PhotoImage(image)
            image_label.configure(image=state['image'], text='')
            state['total'] = total
            page_label.set(f"Pagina {state['page'] + 1} di {total}")
        except Exception:
            state['image'] = None; image_label.configure(image='', text='Anteprima non disponibile.')
            state['total'] = 1; page_label.set('')

    def load():
        row = state['rows'][state['index']]
        status.set(f"Documento {state['index'] + 1} di {len(state['rows'])}")
        for name, value in entries.items(): value.set(row[name])
        state['page'] = 0; preview()

    def collect():
        try:
            state['rows'] = edit_reference(state['rows'], state['index'], {name: value.get() for name, value in entries.items()})
            return True
        except ValueError:
            messagebox.showerror('Dati non validi', 'Controlla ruolo, lingua e lunghezza dei campi.', parent=window)
            return False

    def move(delta):
        if collect() and 0 <= state['index'] + delta < len(state['rows']):
            state['index'] += delta; load()

    def move_page(delta):
        if 0 <= state['page'] + delta < state['total']:
            state['page'] += delta; preview()

    def save():
        if not collect(): return
        try:
            path = save_reference_draft(private_root, state['rows'])
            state['last_saved'] = serialize_reference(state['rows'])
            messagebox.showinfo('Bozza salvata', f'Nuova bozza locale:\n{path.name}\n\nIl foglio originale non è stato modificato. La bozza richiede verifica e approvazione prima dell’OCR.', parent=window)
        except ValueError:
            messagebox.showerror('Salvataggio non riuscito', 'Non è stato possibile salvare la bozza nella cartella privata.', parent=window)

    def add_documents():
        if not collect(): return
        selected = filedialog.askopenfilenames(parent=window, initialdir=str(authorised_root),
                                               title='Scegli documenti nella cartella autorizzata')
        if not selected: return
        try:
            for path in selected:
                if Path(path).suffix.lower() not in {'.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.gif', '.bmp'}:
                    raise ValueError('unsupported format')
                with open_local_file(authorised_root, path):
                    pass
            first_new = len(state['rows'])
            state['rows'] = add_reference_documents(state['rows'], list(selected))
            state['index'] = first_new; load()
        except (OSError, ValueError):
            messagebox.showerror('Selezione non valida', 'Scegli file distinti nella cartella autorizzata, fino a 50 documenti in totale.', parent=window)

    def remove_document():
        if not collect(): return
        if len(state['rows']) <= 1:
            messagebox.showerror('Selezione non valida', 'La bozza deve conservare almeno un documento.', parent=window)
            return
        if not messagebox.askyesno('Rimuovi dal campione', 'Rimuovere questo documento dalla bozza? Il file originale non sarà cancellato. Aggiorna eventuali corrispondenze già compilate.', parent=window):
            return
        state['rows'] = remove_reference_document(state['rows'], state['index'])
        state['index'] = min(state['index'], len(state['rows']) - 1); load()

    def edit_matches():
        if not collect(): return
        notes = [(row['codice'], f"{index + 1} — {Path(row['percorso_locale']).name}")
                 for index, row in enumerate(state['rows']) if row['ruolo'] == 'nota']
        receipts = [(row['codice'], f"{index + 1} — {Path(row['percorso_locale']).name}")
                    for index, row in enumerate(state['rows']) if row['ruolo'] == 'giustificativo']
        if not notes or not receipts:
            messagebox.showinfo('Prima scegli i ruoli', 'Indica almeno una nota e un giustificativo nel foglio.', parent=window)
            return
        dialog = tk.Toplevel(window); dialog.title('Abbinamenti manuali'); dialog.geometry('720x540')
        frame = ttk.Frame(dialog, padding=12); frame.pack(expand=True, fill='both')
        ttk.Label(frame, text='Indica la riga della nota e il suo giustificativo univoco.', wraplength=680).pack(anchor='w')
        ttk.Label(frame, text='Nota').pack(anchor='w')
        note_box = ttk.Combobox(frame, values=[label for _, label in notes], state='readonly', width=75); note_box.pack(anchor='w')
        ttk.Label(frame, text='Giustificativo').pack(anchor='w')
        receipt_box = ttk.Combobox(frame, values=[label for _, label in receipts], state='readonly', width=75); receipt_box.pack(anchor='w')
        coords = ttk.Frame(frame); coords.pack(anchor='w', pady=6)
        ttk.Label(coords, text='Pagina della nota (da 1)').pack(side='left')
        page_entry = ttk.Entry(coords, width=6); page_entry.pack(side='left', padx=4)
        ttk.Label(coords, text='Posizione della riga nella pagina (da 1)').pack(side='left')
        row_entry = ttk.Entry(coords, width=6); row_entry.pack(side='left', padx=4)
        listing = tk.Listbox(frame, height=10); listing.pack(expand=True, fill='both', pady=6)

        def show_selected(choices, box):
            if box.current() < 0:
                messagebox.showerror('Selezione incompleta', 'Scegli prima un documento.', parent=dialog); return
            code = choices[box.current()][0]
            path = next(row['percorso_locale'] for row in state['rows'] if row['codice'] == code)
            view = tk.Toplevel(dialog); view.title('Anteprima locale'); view.geometry('720x760')
            label = ttk.Label(view, anchor='center'); label.pack(expand=True, fill='both')
            controls = ttk.Frame(view); controls.pack(fill='x')
            current = {'page': 0, 'total': 1, 'image': None}
            counter = tk.StringVar(); ttk.Label(controls, textvariable=counter).pack(side='left')
            def render(delta=0):
                number = current['page'] + delta
                if not 0 <= number < current['total']: return
                try:
                    image, total = _preview(authorised_root, path, number)
                    current.update(page=number, total=total, image=ImageTk.PhotoImage(image))
                    label.configure(image=current['image']); counter.set(f'Pagina {number + 1} di {total}')
                except Exception:
                    label.configure(text='Anteprima non disponibile.'); counter.set('')
            ttk.Button(controls, text='Pagina precedente', command=lambda: render(-1)).pack(side='left', padx=4)
            ttk.Button(controls, text='Pagina successiva', command=lambda: render(1)).pack(side='left')
            render()

        def refresh():
            listing.delete(0, tk.END)
            labels = {code: label for code, label in notes + receipts}
            for item in state['matches']:
                listing.insert(tk.END, f"Nota {labels.get(item['codice_nota'], '?')} — pagina {item['pagina']}, riga {item['posizione']} → {labels.get(item['codice_documento_corretto'], '?')}")

        def add_match():
            if note_box.current() < 0 or receipt_box.current() < 0:
                messagebox.showerror('Selezione incompleta', 'Scegli una nota e un giustificativo.', parent=dialog); return
            try:
                state['matches'] = add_manual_match(state['rows'], state['matches'], notes[note_box.current()][0],
                                                    receipts[receipt_box.current()][0], page_entry.get().strip(), row_entry.get().strip())
                refresh()
            except ValueError:
                messagebox.showerror('Abbinamento non valido', 'Controlla ruoli, pagina e posizione: ogni riga può comparire una sola volta.', parent=dialog)

        def remove_match():
            selected = listing.curselection()
            if selected:
                state['matches'] = [item for index, item in enumerate(state['matches']) if index != selected[0]]; refresh()

        def save_matches():
            try:
                directory = save_matching_drafts(private_root, state['rows'], state['matches'])
                state['matches_saved'] = [dict(item) for item in state['matches']]
                messagebox.showinfo('Bozza salvata', f'Abbinamenti e posizioni salvati nella nuova cartella privata:\n{directory.name}\n\nVerifica e approva il riferimento prima dell’OCR.', parent=dialog)
            except ValueError:
                messagebox.showerror('Salvataggio non riuscito', 'Controlla che gli abbinamenti usino documenti ancora presenti e che la cartella privata sia accessibile.', parent=dialog)

        def load_matches():
            directory = filedialog.askdirectory(parent=dialog, initialdir=str(private_root), title='Scegli una cartella di abbinamenti salvata')
            if not directory: return
            if state['matches'] != state['matches_saved'] and not messagebox.askyesno('Modifiche non salvate', 'Sostituire gli abbinamenti non salvati?', parent=dialog): return
            try:
                state['matches'] = load_matching_drafts(private_root, state['rows'], directory)
                state['matches_saved'] = [dict(item) for item in state['matches']]; refresh()
            except ValueError:
                messagebox.showerror('Apertura non riuscita', 'La coppia di file non è valida o non corrisponde al campione aperto.', parent=dialog)

        actions = ttk.Frame(frame); actions.pack(fill='x')
        ttk.Button(actions, text='Aggiungi', command=add_match).pack(side='left')
        ttk.Button(actions, text='Rimuovi selezionato', command=remove_match).pack(side='left', padx=4)
        ttk.Button(actions, text='Salva bozza', command=save_matches).pack(side='left', padx=4)
        ttk.Button(actions, text='Apri bozza', command=load_matches).pack(side='left')
        previews = ttk.Frame(frame); previews.pack(fill='x', pady=4)
        ttk.Button(previews, text='Mostra nota', command=lambda: show_selected(notes, note_box)).pack(side='left')
        ttk.Button(previews, text='Mostra giustificativo', command=lambda: show_selected(receipts, receipt_box)).pack(side='left', padx=4)
        refresh(); dialog.transient(window); dialog.grab_set()

    controls = ttk.Frame(left); controls.pack(fill='x', pady=10)
    ttk.Button(controls, text='Documento precedente', command=lambda: move(-1)).pack(side='left')
    ttk.Button(controls, text='Documento successivo', command=lambda: move(1)).pack(side='left', padx=5)
    selection = ttk.Frame(left); selection.pack(fill='x', pady=(0, 8))
    ttk.Button(selection, text='Aggiungi documenti', command=add_documents).pack(side='left')
    ttk.Button(selection, text='Rimuovi dal campione', command=remove_document).pack(side='left', padx=5)
    ttk.Button(left, text='Gestisci abbinamenti', command=edit_matches).pack(fill='x', pady=(0, 6))
    ttk.Button(left, text='Salva una nuova bozza', command=save).pack(fill='x')
    ttk.Button(page_controls, text='Pagina precedente', command=lambda: move_page(-1)).pack(side='left', padx=6)
    ttk.Button(page_controls, text='Pagina successiva', command=lambda: move_page(1)).pack(side='left')
    def close():
        if not collect(): return
        if ((serialize_reference(state['rows']) != state['last_saved'] or state['matches'] != state['matches_saved'])
                and not messagebox.askyesno('Modifiche non salvate', 'Chiudere senza salvare le modifiche?', parent=window)):
            return
        window.destroy()
    window.protocol('WM_DELETE_WINDOW', close)
    load()
    window.mainloop()


def choose_reference(private_root):
    picker = tk.Tk()
    try:
        picker.withdraw()
        selection = filedialog.askopenfilename(parent=picker, initialdir=str(private_root),
                                               title='Scegli il foglio o una bozza salvata',
                                               filetypes=[('Fogli CSV', '*.csv')])
        return selection or None
    finally:
        picker.destroy()


def main():
    parser = argparse.ArgumentParser(description='Preparazione manuale locale del foglio')
    parser.add_argument('--private-root', required=True)
    parser.add_argument('--sheet')
    parser.add_argument('--document-root', required=True)
    args = parser.parse_args()
    try:
        sheet = args.sheet or choose_reference(args.private_root)
        if sheet is None:
            return 0
        run(args.private_root, sheet, args.document_root)
    except Exception:
        messagebox.showerror('OCR2', 'Impossibile aprire la guida locale o il foglio selezionato.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
