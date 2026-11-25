"""Stable retained-unit coordinates. Never invent page geometry or original/derivative maps."""
import re

def anchors(units,*,source_id=None,artifact_id=None):
    result=[]
    for u in units:
        locator=u['locator'];kind='text';extra={}
        if artifact_id:kind='sanitized_section'
        elif match:=re.match(r'^Page ([0-9]+)',locator):kind='pdf_page';extra['page']=int(match[1])
        elif match:=re.fullmatch(r'Paragraph ([0-9]+)',locator):kind='paragraph';extra['paragraph']=int(match[1])
        elif match:=re.fullmatch(r'Table ([0-9]+), row ([0-9]+)',locator):kind='table_row';extra.update({'table':int(match[1]),'row':int(match[2])})
        elif u.get('sheet')=='CSV':kind='csv_row';extra['row']=u['row']
        elif u.get('sheet'):
            kind='sheet_cells';extra.update({'sheet':u['sheet'],'row':u['row'],'cells':[c['coordinate'] for c in u['cells']]})
        elif match:=re.fullmatch(r'(.+), row ([0-9]+)',locator):kind='sheet_cells';extra.update({'sheet':match[1],'row':int(match[2]),'cells':None})
        result.append({'schema':'kestrel-citation-anchor-1','document_version_id':source_id,'artifact_id':artifact_id,'kind':kind,'unit':u['number'],'start':0,'end':len(u['text']),'locator':locator,
            'bounding_box':None,'coordinate_map_status':'sanitized_coordinates_only' if artifact_id else 'retained_text_offsets',**extra})
    return result
