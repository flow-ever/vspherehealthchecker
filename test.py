import os
from decimal import Decimal

x = round(5.76543, 1)
print(x)

value=1.00023
y=Decimal(value).quantize(Decimal('0'))
print(y)