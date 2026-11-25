"""Export model structure only. Never connects to a database or reads row data."""
import csv
import json
from pathlib import Path
from kestrel.models import Base


def field_meaning(column):
    if column.doc or column.comment:
        return column.doc or column.comment, 'Model documentation'
    name = column.name
    if column.primary_key:
        return 'Stable identifier for this record.', 'Inferred from declared primary key'
    if column.foreign_keys:
        targets = ', '.join(sorted(f.target_fullname for f in column.foreign_keys))
        return f'Connects this record to {targets}.', 'Declared foreign key'
    if name.endswith(('_at', '_time')):
        return f'Records when {name.replace("_", " ")} applies. Confirm encoding and clock rules in the service.', 'Name-based explanation; verify service semantics'
    if 'hash' in name or 'digest' in name:
        return 'Digest used for integrity, version binding or protected lookup. Check the service for its precise input and algorithm.', 'Name-based explanation; verify service semantics'
    if name.endswith('_id'):
        return f'Identifier reference named {name}; no database foreign key is declared on this column.', 'Observed name and absence of declared foreign key'
    return f'{name.replace("_", " ").capitalize()} for this record. Type and nullability are declared below; business rules are enforced by the API and service.', 'Name-based explanation; verify service semantics'


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'backend/kestrel/data/resource_library'
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    entities = []
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        entities.append({'table': table.name, 'field_count': len(table.columns), 'schema_status': 'IMPLEMENTED MODEL SNAPSHOT'})
        for column in table.columns:
            definition, basis = field_meaning(column)
            rows.append({'table': table.name, 'field': column.name, 'type': str(column.type),
                         'nullable': column.nullable, 'primary_key': column.primary_key,
                         'foreign_keys': '; '.join(sorted(f.target_fullname for f in column.foreign_keys)),
                         'unique': bool(column.unique), 'definition': definition, 'definition_basis': basis,
                         'schema_status': 'IMPLEMENTED MODEL SNAPSHOT',
                         'source': 'backend/kestrel/models.py', 'as_of': '2026-11-24'})
    for name, values in [('Implemented_Schema_Fields.csv', rows), ('Implemented_Schema_Tables.csv', entities)]:
        with (target / name).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0])); writer.writeheader(); writer.writerows(values)
    print(json.dumps({'tables': len(entities), 'fields': len(rows), 'contains_row_data': False}))
