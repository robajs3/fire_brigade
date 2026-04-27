from smartcard.System import readers
from smartcard.util import toHexString
from smartcard.CardMonitoring import CardMonitor, CardObserver
import time

class MyObserver(CardObserver):
    def update(self, observable, actions):
        added, removed = actions
        for card in added:
            print("Karta wykryta! ATR:", toHexString(card.atr))

print("Połóż kartę na czytniku i trzymaj nieruchomo...")
monitor = CardMonitor()
observer = MyObserver()
monitor.addObserver(observer)

try:
    time.sleep(15)
except KeyboardInterrupt:
    pass

monitor.deleteObserver(observer)
print("Koniec")