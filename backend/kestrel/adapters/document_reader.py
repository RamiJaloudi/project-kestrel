"""Read-only presentation data from bounded originals; never returns executable Office HTML."""
import io
import json
from pathlib import PurePath
from fastapi import HTTPException

def presentation(row):
    units=json.loads(row.units_json)
    ext=PurePath(row.file_name).suffix.lower()
    result={'format':{'.pdf':'pdf','.docx':'word','.xlsx':'excel'}.get(ext,'text'),
        'units':units,'blocks':[],'sheets':[]}
    by_locator={u['locator']:u for u in units}
    if units and ('cells' in units[0] or units[0].get('workbook_sheets')):
        result['format']='excel';sheets={s['name']:{'name':s['name'],'state':s['state'],'columns':0,'rows':[]} for s in units[0].get('workbook_sheets',[])}
        for unit in units:
            if 'cells' not in unit:continue
            name=unit['sheet'];sheet=sheets.setdefault(name,{'name':name,'state':unit['sheet_state'],'columns':0,'rows':[]})
            sheet['columns']=max(sheet['columns'],max((c['column'] for c in unit['cells']),default=0))
            sheet['rows'].append({'number':unit['row'],'unit':unit['number'],'cells':unit['cells']})
        result['sheets']=list(sheets.values());return result
    if ext=='.xlsx':
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(row.data),read_only=True,data_only=False,keep_links=False)
        try:
            count=0
            for sheet in book:
                rows=[];width=0
                for index,cells in enumerate(sheet.iter_rows(),1):
                    count+=len(cells)
                    if index>1000 or len(cells)>50 or count>5000:raise HTTPException(413,'Reader workbook limit exceeded')
                    unit=by_locator.get(f'{sheet.title}, row {index}')
                    if not unit:continue
                    values=[]
                    for column,cell in enumerate(cells,1):
                        if cell.data_type=='f':raise HTTPException(422,'Formula workbook unavailable')
                        if cell.value is not None:
                            values.append({'column':column,'coordinate':cell.coordinate,'text':str(cell.value)})
                            width=max(width,column)
                    rows.append({'number':index,'unit':unit['number'],'cells':values})
                result['sheets'].append({'name':sheet.title,'columns':width,'rows':rows})
        finally:book.close()
    elif ext=='.docx':
        from docx import Document
        from docx.table import Table
        doc=Document(io.BytesIO(row.data));paragraph_index=table_index=0
        for element in doc.element.body:
            if element.tag.endswith('}p'):
                paragraph_index+=1;unit=by_locator.get(f'Paragraph {paragraph_index}')
                if unit:result['blocks'].append({'kind':'paragraph','unit':unit['number']})
            elif element.tag.endswith('}tbl'):
                table_index+=1
                for index,cells in enumerate(Table(element,doc).rows,1):
                    unit=by_locator.get(f'Table {table_index}, row {index}')
                    if unit:result['blocks'].append({'kind':'table_row','unit':unit['number'],'table':table_index,'cells':[cell.text for cell in cells.cells]})
    else:result['blocks']=[{'kind':'text','unit':u['number']} for u in units]
    return result
