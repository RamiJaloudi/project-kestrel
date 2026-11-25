"""Single inventory of local portal/Swagger launch targets. No browser automation."""
import ast
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]


def targets():
    return [{'name':'Portal Home','url':'https://localhost:8443/'}]


def all_targets():
    groups={}
    tree=ast.parse((root/'backend/kestrel/preview.py').read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GROUPS' for t in node.targets):
            groups=ast.literal_eval(node.value)
    rows=[]
    for host,label in [('admin.localhost','Administration'),('firm.localhost','Firm'),
                       ('client.localhost','Halden'),('bank.localhost','Castlegate')]:
        rows.append({'name':label+' portal / login','url':f'https://{host}:8443/portal'})
    rows.append({'name':'Shared API full Swagger','url':'https://admin.localhost:8443/docs'})
    rows.extend({'name':name+' API Swagger','url':'https://admin.localhost:8443/docs/'+name} for name in groups)
    return rows


if __name__=='__main__':
    print(json.dumps(targets()))
