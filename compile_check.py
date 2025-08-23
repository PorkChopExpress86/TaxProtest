import py_compile, sys
try:
    py_compile.compile(r'e:\TaxProtest\extract_data.py', doraise=True)
    print('OK')
except Exception as e:
    print('FAIL:', e)
