"""Manual local reference editor. Opens no network connections and runs no OCR."""
from __future__ import annotations

import argparse
import io
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from tools.field_trial_editor import EDITABLE, edit_reference, save_reference_draft, serialize_reference
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
             'last_saved': serialize_reference(rows)}

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

    controls = ttk.Frame(left); controls.pack(fill='x', pady=10)
    ttk.Button(controls, text='Documento precedente', command=lambda: move(-1)).pack(side='left')
    ttk.Button(controls, text='Documento successivo', command=lambda: move(1)).pack(side='left', padx=5)
    ttk.Button(left, text='Salva una nuova bozza', command=save).pack(fill='x')
    ttk.Button(page_controls, text='Pagina precedente', command=lambda: move_page(-1)).pack(side='left', padx=6)
    ttk.Button(page_controls, text='Pagina successiva', command=lambda: move_page(1)).pack(side='left')
    def close():
        if not collect(): return
        if (serialize_reference(state['rows']) != state['last_saved']
                and not messagebox.askyesno('Modifiche non salvate', 'Chiudere senza salvare le modifiche?', parent=window)):
            return
        window.destroy()
    window.protocol('WM_DELETE_WINDOW', close)
    load()
    window.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Preparazione manuale locale del foglio')
    parser.add_argument('--private-root', required=True)
    parser.add_argument('--sheet', required=True)
    parser.add_argument('--document-root', required=True)
    args = parser.parse_args()
    try:
        run(args.private_root, args.sheet, args.document_root)
    except Exception:
        messagebox.showerror('OCR2', 'Impossibile aprire la guida locale o il foglio selezionato.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
