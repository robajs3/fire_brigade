import os
# Ustaw PATH przed importem pyrfc żeby Windows znalazł DLL
os.environ["PATH"] = r"D:\Programs\nwrfc\nwrfcsdk\lib;" + os.environ.get("PATH", "")

from datetime import date
from config import Config

try:
    from pyrfc import (
        Connection,
        ABAPApplicationError,
        ABAPRuntimeError,
        CommunicationError,
        LogonError,
    )
    PYRFC_AVAILABLE = True
except (ImportError, Exception):
    PYRFC_AVAILABLE = False
    class Connection:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("pyrfc / SAP NW RFC SDK niedostępny")
    ABAPApplicationError = Exception
    ABAPRuntimeError     = Exception
    CommunicationError   = Exception
    LogonError           = Exception


def _get_connection():
    if not PYRFC_AVAILABLE:
        raise RuntimeError("pyrfc niedostępny")
    return Connection(**Config.get_sap_config())


class SAPService:

    @staticmethod
    def get_stock():
        conn = None
        try:
            conn = _get_connection()
            result = conn.call(
                "ZDSP_WERKSTOCK",
                I_WERK=Config.SAP_WERK,
                I_LGORT=Config.SAP_LGORT,
                I_EMPTY=" ",
                I_USAGE="X",
            )
            stock = []
            for row in result.get("STOCK_TAB", []):
                matnr = row.get("MATNR", "").strip().lstrip("0")
                labst = float(row.get("LABST", 0) or 0)
                stock.append({
                    "matnr":     matnr,
                    "matnr_raw": row.get("MATNR", "").strip(),
                    "maktx":     row.get("MAKTX", "").strip(),
                    "labst":     labst,
                    "mei":       row.get("MEI", "").strip(),
                    "dmbtr":     float(row.get("DMBTR", 0) or 0),
                    "lgort":     row.get("LGORT", "").strip(),
                    "werk":      row.get("WERK", "").strip(),
                })
            return stock
        except (ABAPApplicationError, ABAPRuntimeError,
                CommunicationError, LogonError) as e:
            print(f"[SAP] Błąd pobierania stanu: {e}")
            return []
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_stock_for_matnr(matnr):
        stock = SAPService.get_stock()
        matnr_clean = matnr.strip().lstrip("0")
        for item in stock:
            if item["matnr"] == matnr_clean:
                return item
        return None

    @staticmethod
    def post_goods_issue(matnr, menge, meins, kostl, ref_doc=None):
        conn = None
        try:
            conn = _get_connection()
            today = date.today().strftime("%Y-%m-%d")
            header = {
                "PSTNG_DATE": today,
                "DOC_DATE":   today,
                "PR_UNAME":   "MAGAZYN",
                "REF_DOC_NO": ref_doc or "SP-MAGAZYN",
                "HEADER_TXT": "Wydanie dla strazy pozarnej",
            }
            item = {
                "MATERIAL":   matnr.zfill(18),
                "PLANT":      Config.SAP_WERK,
                "STGE_LOC":   Config.SAP_LGORT,
                "MOVE_TYPE":  "201",
                "ENTRY_QNT":  menge,
                "ENTRY_UOM":  meins,
                "COSTCENTER": kostl,
            }
            result = conn.call(
                "BAPI_GOODSMVT_CREATE",
                GOODSMVT_HEADER=header,
                GOODSMVT_CODE={"GM_CODE": "04"},
                GOODSMVT_ITEM=[item],
            )
            return_msgs = result.get("RETURN", [])
            errors = [
                r["MESSAGE"] for r in return_msgs
                if r.get("TYPE") in ("E", "A")
            ]
            if errors:
                print(f"[SAP] Błąd BAPI: {errors}")
                return {"success": False, "error": "; ".join(errors)}
            conn.call("BAPI_TRANSACTION_COMMIT", WAIT="X")
            mblnr = result.get("MATERIALDOCUMENT", "")
            print(f"[SAP] Wydano materiał {matnr}, dok. {mblnr}")
            return {"success": True, "mblnr": mblnr}
        except (ABAPApplicationError, ABAPRuntimeError,
                CommunicationError, LogonError) as e:
            print(f"[SAP] Błąd wydania: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()

    @staticmethod
    def post_goods_return(matnr, menge, meins, kostl, ref_doc=None):
        conn = None
        try:
            conn = _get_connection()
            today = date.today().strftime("%Y-%m-%d")
            header = {
                "PSTNG_DATE": today,
                "DOC_DATE":   today,
                "PR_UNAME":   "MAGAZYN",
                "REF_DOC_NO": ref_doc or "SP-ZWROT",
                "HEADER_TXT": "Zwrot do magazynu - straz pozarna",
            }
            item = {
                "MATERIAL":   matnr.zfill(18),
                "PLANT":      Config.SAP_WERK,
                "STGE_LOC":   Config.SAP_LGORT,
                "MOVE_TYPE":  "202",
                "ENTRY_QNT":  menge,
                "ENTRY_UOM":  meins,
                "COSTCENTER": kostl,
            }
            result = conn.call(
                "BAPI_GOODSMVT_CREATE",
                GOODSMVT_HEADER=header,
                GOODSMVT_CODE={"GM_CODE": "04"},
                GOODSMVT_ITEM=[item],
            )
            return_msgs = result.get("RETURN", [])
            errors = [
                r["MESSAGE"] for r in return_msgs
                if r.get("TYPE") in ("E", "A")
            ]
            if errors:
                return {"success": False, "error": "; ".join(errors)}
            conn.call("BAPI_TRANSACTION_COMMIT", WAIT="X")
            mblnr = result.get("MATERIALDOCUMENT", "")
            return {"success": True, "mblnr": mblnr}
        except (ABAPApplicationError, ABAPRuntimeError,
                CommunicationError, LogonError) as e:
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()

    @staticmethod
    def sync_stock_to_catalog():
        """
        Synchronizuje stan SAP → tabela items (magazyn fizyczny).
        - Dla każdego materiału z SAP sprawdza ile sztuk jest w magazynie
          (items gdzie firefighter_id IS NULL i is_consumed=False)
        - Jeśli SAP ma więcej – dodaje brakujące sztuki do items
        - Przedmiotów dodanych ręcznie (bez catalog_id z SAP) nie dotyka
        """
        from models.item_model import Item, ItemCatalog
        from models.user_model import db

        stock = SAPService.get_stock()
        if not stock:
            return {"updated": 0, "created": 0, "total": 0}

        # Zaktualizuj sap_stock w katalogu
        existing_catalogs = {
            c.sap_matnr.strip(): c
            for c in ItemCatalog.query.filter(
                ItemCatalog.sap_matnr.isnot(None)
            ).all()
        }

        added = 0

        for row in stock:
            matnr_raw = row["matnr_raw"]
            matnr     = row["matnr"]
            maktx     = row["maktx"]
            labst     = int(row["labst"])  # ilość sztuk z SAP
            mei       = (row["mei"] or "szt").lower()

            # Znajdź lub utwórz pozycję w katalogu
            cat = existing_catalogs.get(matnr_raw) or existing_catalogs.get(matnr)

            if not cat:
                # Nowy materiał z SAP – dodaj do katalogu
                cat = ItemCatalog(
                    name=maktx,
                    unit_of_measure=mei,
                    sap_matnr=matnr_raw,
                    sap_stock=labst,
                    is_active=True
                )
                db.session.add(cat)
                db.session.flush()  # żeby mieć catalog_id
                existing_catalogs[matnr_raw] = cat
            else:
                cat.sap_stock = labst

            # Policz ile sztuk tego materiału jest w magazynie (nie wydanych, nie zużytych)
            in_stock_count = Item.query.filter_by(
                catalog_id=cat.catalog_id,
                is_consumed=False
            ).filter(Item.firefighter_id.is_(None)).count()

            # Policz wszystkie aktywne (w magazynie + wydane)
            total_active = Item.query.filter_by(
                catalog_id=cat.catalog_id,
                is_consumed=False
            ).count()

            # Dodaj brakujące sztuki (tylko do stanu magazynowego)
            to_add = labst - total_active
            if to_add > 0:
                for _ in range(to_add):
                    new_item = Item(
                        name=maktx,
                        unit_of_measure=mei,
                        catalog_id=cat.catalog_id,
                        is_consumed=False
                    )
                    db.session.add(new_item)
                    added += 1

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[SAP] Błąd synchronizacji: {e}")
            return {"updated": 0, "created": 0, "total": 0}

        print(f"[SAP] Synchronizacja: dodano {added} sztuk do magazynu")
        return {"updated": 0, "created": added, "total": added}