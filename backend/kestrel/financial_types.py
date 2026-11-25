from decimal import Decimal
from sqlalchemy.types import TypeDecorator,Numeric,String

class ExactFinancialDecimal(TypeDecorator):
    """PostgreSQL NUMERIC; exact strings in isolated SQLite tests, never binary float."""
    impl=Numeric(38,12)
    cache_ok=True
    def load_dialect_impl(self,dialect):return dialect.type_descriptor(String(64) if dialect.name=='sqlite' else Numeric(38,12))
    def process_bind_param(self,value,dialect):
        if value is None:return None
        if isinstance(value,float):raise ValueError('Binary floating-point amounts are not accepted')
        from kestrel.adapters.financial import canonical_amount
        return canonical_amount(Decimal(value)) if dialect.name=='sqlite' else Decimal(value)
    def process_result_value(self,value,dialect):return None if value is None else Decimal(str(value))
