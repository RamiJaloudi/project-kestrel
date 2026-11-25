from decimal import Decimal
import pytest
from fastapi import HTTPException

def test_declared_numeric_convention_sign_scale_and_no_float_rounding():
 from kestrel.adapters.financial import number,base_amount,compare
 assert number('(1.250,50)',',')==Decimal('-1250.50')
 assert number('1,250.50','.')==Decimal('1250.50')
 assert number('125000','.')==Decimal('125000')
 assert number('9007199254740993.125','.')==Decimal('9007199254740993.125')
 assert number('1.2500e6','.',scientific=True)==Decimal('1250000')
 assert number('-1,25E3',',',scientific=True)==Decimal('-1250')
 assert base_amount(number('1234.50','.'),'1000')==Decimal('1234500.00')
 assert compare('125000','100000')=={'difference':'25000','percentage_change':'25'}
 with pytest.raises(HTTPException):number('1,23,456','.')
 with pytest.raises(HTTPException):number('NaN','.')
 with pytest.raises(HTTPException):number('1e9','.')
 with pytest.raises(HTTPException):base_amount(Decimal('9'*28),'1000000')
 assert compare('10','0')['percentage_change'] is None
