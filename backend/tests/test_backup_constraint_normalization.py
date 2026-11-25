"""Accept only PostgreSQL's equivalent literal enum-array restore spelling."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('recovery_verifier',Path(__file__).resolve().parents[2]/'scripts/verify_database_recovery.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
normalize=module.normalized_constraint

def test_fixed_varchar_enum_array_cast_roundtrip():
    source="CHECK (((kind)::text = ANY ((ARRAY['source'::character varying, 'financial'::character varying])::text[])))"
    restored="CHECK (((kind)::text = ANY (ARRAY[('source'::character varying)::text, ('financial'::character varying)::text])))"
    assert normalize(source)==restored
    assert normalize(restored)==restored
    assert normalize(source.replace('financial','other'))!=normalize(restored)

def test_arbitrary_or_length_constrained_casts_are_not_erased():
    for value in ["CHECK (kind=ANY((ARRAY[column_value])::text[]))", "CHECK (kind=ANY((ARRAY['source'::character varying(2)])::text[]))", "CHECK (amount>0)"]:
        assert normalize(value)==value

def test_quoted_commas_and_apostrophes_remain_exact():
    source="CHECK (v=ANY((ARRAY['a,b'::character varying, 'it''s'::character varying])::text[]))"
    target="CHECK (v=ANY(ARRAY[('a,b'::character varying)::text, ('it''s'::character varying)::text]))"
    assert normalize(source)==target
    assert normalize(source)!=normalize(source.replace("it''s","its"))
