from pathlib import Path
import pytest
from services.importacion_borradores_contables import importar_borradores

class Obj:
    siguiente=1
    def __init__(self,**datos):self.__dict__.update(datos);self.id=getattr(self,"id",Obj.siguiente);Obj.siguiente+=1
class Session:
    def __init__(self):self.objetos=[];self.commits=0;self.rollbacks=0
    def add(self,x):self.objetos.append(x)
    def flush(self):pass
    def commit(self):self.commits+=1
    def rollback(self):self.rollbacks+=1

def cuentas():return [Obj(id=1,codigo="1.1",organizacion_id=7,unidad_negocio_id=9,imputable=True),Obj(id=2,codigo="4.1",organizacion_id=7,unidad_negocio_id=9,imputable=True),Obj(id=3,codigo="2.1",organizacion_id=7,unidad_negocio_id=9,imputable=True)]

def test_importa_asiento_multilinea_en_una_transaccion():
    datos=b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1.1,Caja,100,0\nA,2026-10-01,2.1,Impuesto,20,0\nA,2026-10-01,4.1,Venta,0,120\n";s=Session()
    creados=importar_borradores(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv",cuentas=cuentas(),Asiento=Obj,Linea=Obj,db_session=s,usuario_id=5)
    assert len(creados)==1 and len(s.objetos)==4 and s.commits==1
    assert creados[0].total_debe_centavos==creados[0].total_haber_centavos==12000
    assert creados[0].contabilizado is False and all(getattr(x,"afecta_saldos",False) is False for x in s.objetos)

def test_importa_varios_asientos_y_claves_distintas():
    datos=b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1.1,X,10,0\nA,2026-10-01,4.1,X,0,10\nB,2026-10-02,1.1,Y,20,0\nB,2026-10-02,4.1,Y,0,20\n";s=Session()
    creados=importar_borradores(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv",cuentas=cuentas(),Asiento=Obj,Linea=Obj,db_session=s)
    assert len(creados)==2 and creados[0].clave_idempotencia!=creados[1].clave_idempotencia

def test_rechaza_desbalance_cuentas_faltantes_y_cruces():
    casos=[b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1.1,X,10,0\nA,2026-10-01,4.1,X,0,9\n",
           b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,9.9,X,10,0\nA,2026-10-01,4.1,X,0,10\n"]
    for datos in casos:
        with pytest.raises(ValueError):importar_borradores(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv",cuentas=cuentas(),Asiento=Obj,Linea=Obj,db_session=Session())

def test_rechaza_errores_y_duplicados_antes_de_escribir():
    datos=b"asiento,fecha,cuenta,concepto,debe,haber\nA,2026-10-01,1.1,X,10,0\nA,2026-10-01,1.1,X,10,0\nA,2026-10-01,4.1,X,0,20\n";s=Session()
    with pytest.raises(ValueError):importar_borradores(organizacion_id=7,unidad_negocio_id=9,contenido=datos,nombre_archivo="x.csv",cuentas=cuentas(),Asiento=Obj,Linea=Obj,db_session=s)
    assert not s.objetos and s.commits==0

def test_modelo_linea_impide_impacto_y_partidas_mixtas():
    texto=Path("models/contabilidad.py").read_text(encoding="utf-8")
    assert "linea_asiento_contable_borrador" in texto and "uq_linea_asiento_borrador_renglon" in texto
    assert "afecta_saldos = false" in texto and "debe_centavos > 0 AND haber_centavos = 0" in texto

def test_ruta_y_frontera_importacion():
    rutas=Path("modules/admin/contabilidad/routes.py").read_text(encoding="utf-8");panel=Path("templates/admin_contabilidad.html").read_text(encoding="utf-8")
    servicio=Path("services/importacion_borradores_contables.py").read_text(encoding="utf-8")
    assert 'route("/admin/contabilidad/importar-borradores",methods=["POST"])' in rutas and "Importar asientos como borrador" in panel
    for termino in ("requests.","urlopen","LibroDiario","contabilizado=True","afecta_saldos=True"):assert termino not in servicio
