"""Public openpyxl authoring worker. Never evaluates formulas or loads macros."""
import io
import json
import math
import re
import sys
import textwrap
from datetime import date
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]


def literal(cell, value):
    if value is not None and not isinstance(value, (str, int, float, bool, date)):
        raise ValueError('Unsupported cell type')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Nonfinite number')
    if isinstance(value, str) and (len(value) > 32767 or any(ord(c) < 32 and c not in '\n\r\t' for c in value)):
        raise ValueError('Unsafe cell text')
    cell.value = value
    if isinstance(value, str):
        # Explicit string typing preserves the literal without a visible apostrophe.
        cell.data_type = 's'
        cell.number_format = '@'
        cell.quotePrefix = bool(value and value[0] in '=+-@\t\r\n')


def preview(book):
    """Bounded raster previews for the existing synthetic tracker lab."""
    from PIL import Image, ImageDraw, ImageFont
    folder = ROOT / 'outputs/tracker-previews'
    folder.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=14)
    for sheet in book:
        columns = min(sheet.max_column, 16)
        width = min(2600, max(500, columns * 220))
        col_width = width // columns
        rows = list(sheet.iter_rows(max_row=min(sheet.max_row, 6), values_only=True))
        wrapped = [[textwrap.fill(str(value if value is not None else ''), max(10, col_width // 8)) for value in row] for row in rows]
        heights = [max(48, min(260, max(len(value.splitlines()) for value in row) * 18 + 16)) for row in wrapped]
        image = Image.new('RGB', (width, sum(heights)), 'white')
        draw = ImageDraw.Draw(image)
        top = 0
        for index, (row, height) in enumerate(zip(wrapped, heights)):
            for col, value in enumerate(row):
                box = (col * col_width, top, (col + 1) * col_width, top + height)
                draw.rectangle(box, fill='#193D5D' if index == 0 else '#FFFFFF', outline='#D9D9D9')
                draw.multiline_text((box[0] + 8, top + 8), value, font=font, fill='white' if index == 0 else 'black', spacing=3)
            top += height
        image.save(folder / (re.sub(r'[^A-Za-z0-9_-]', '_', sheet.title) + '.png'))


def tracker(payload):
    if payload.get('existing'):
        raise ValueError('Existing workbooks must pass the tracker import service')
    definitions = payload['sheets']
    if not 1 <= len(definitions) <= 8:
        raise ValueError('Sheet limit exceeded')
    book = Workbook()
    book.remove(book.active)
    names = set()
    for definition in definitions:
        name, rows = definition['name'], definition['rows']
        if not isinstance(name, str) or not name or len(name) > 31 or re.search(r'[\\/*?:\[\]]', name) or name.casefold() in names:
            raise ValueError('Invalid or duplicate sheet name')
        names.add(name.casefold())
        if not rows or len(rows) > 505 or not 1 <= len(rows[0]) <= 16 or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError('Workbook shape exceeded bounds')
        sheet = book.create_sheet(name)
        sheet.sheet_view.showGridLines = False
        sheet.freeze_panes = 'A2'
        headers = rows[0]
        for row_index, row in enumerate(rows, 1):
            max_lines = 1
            for col_index, value in enumerate(row, 1):
                label = str(headers[col_index - 1])
                if row_index > 1 and label == 'DueOn' and isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    try:
                        value = date.fromisoformat(value)
                    except ValueError:
                        pass  # Invalid proposals remain visible to server validation.
                cell = sheet.cell(row_index, col_index)
                literal(cell, value)
                cell.font = Font(name='Arial', size=10, bold=row_index == 1, color='FFFFFF' if row_index == 1 else '000000')
                cell.alignment = Alignment(vertical='center', wrap_text=True)
                wide = bool(re.search(r'Action|Summary|Instructions', label))
                sheet.column_dimensions[get_column_letter(col_index)].width = 48 if wide else 24
                max_lines = max(max_lines, sum(max(1, math.ceil(len(line) / (46 if wide else 22))) for line in str(value or '').split('\n')))
                if row_index == 1:
                    cell.fill = PatternFill('solid', fgColor='193D5D')
                elif label in definition.get('editable', []):
                    cell.fill = PatternFill('solid', fgColor='FFF4D9')
                if isinstance(value, date):
                    cell.number_format = 'yyyy-mm-dd'
                elif label == 'ExpectedRevision' and row_index > 1:
                    cell.number_format = '0'
            sheet.row_dimensions[row_index].height = 32 if row_index == 1 else min(409, max(42, max_lines * 14 + 12))
    if '--preview' in sys.argv:
        preview(book)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def annex(body, status):
    columns = ['reference', 'finding', 'severity', 'materiality', 'requirement', 'action', 'status', 'due_on']
    payload = {'sheets': [{'name': title, 'rows': [
        [title + ' - ' + str(status), *[''] * 7],
        [key.replace('_', ' ') for key in columns],
        *[[str(row[key]) if row.get(key) is not None else '' for key in columns] for row in body[key]],
    ]} for key, title in [('risks', 'Risk annex'), ('consents', 'Consent annex')]]}
    from openpyxl import load_workbook
    book = load_workbook(io.BytesIO(tracker(payload)))
    for sheet in book:
        sheet.merge_cells('A1:H1')
        sheet.freeze_panes = 'A3'
        for cell in sheet[2]:
            cell.fill = PatternFill('solid', fgColor='203C5B')
            cell.font = Font(name='Arial', size=10, color='FFFFFF', bold=True)
        for col in ['B', 'F']:
            sheet.column_dimensions[col].width = 80
        sheet.row_dimensions[1].height = sheet.row_dimensions[2].height = 30
        for row in sheet.iter_rows(min_row=3):
            lines = max(sum(max(1, math.ceil(len(line) / (70 if cell.column in [2, 6] else 22))) for line in str(cell.value or '').split('\n')) for cell in row)
            sheet.row_dimensions[row[0].row].height = min(409, max(60, lines * 14 + 12))
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


if __name__ == '__main__':
    raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Workbook request exceeded bounds')
    sys.stdout.buffer.write(tracker(json.loads(raw)))
