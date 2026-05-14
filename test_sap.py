import os
os.environ['PATH'] = r'D:\Programs\nwrfc\nwrfcsdk\lib;' + os.environ.get('PATH', '')

from services.sap_service import SAPService
stock = SAPService.get_stock()
print('Liczba pozycji:', len(stock))
if stock:
    print('Pierwsza pozycja:', stock[0])
else:
    print('Brak danych - sprawdz logi powyzej')