"""Pruebas de cuenta y movimientos; importes enteros expresados en centavos."""
import unittest
from datetime import date
from types import SimpleNamespace as DTO
from services.saldo_favor_costos import calcular_cuenta
from services.cuentas_pagar_productivas import registrar_pago, anular_pago, saldo_obligacion


def ob(ident,mes,pagos=(),importe=139557850,costo=10,org=7,estado='pendiente'):
    return DTO(id=ident,periodo=date(2026,mes,1),organizacion_id=org,costo_fijo_id=costo,
        importe_centavos=importe,pagos=[DTO(importe_centavos=p,anulado=False) for p in pagos],estado=estado)


class CuentaTests(unittest.TestCase):
    def test_caso_real_dos_pagos_y_mes_siguiente(self):
        nov=ob(1,11,[110000000,30000000]);dic=ob(2,12)
        cuenta=calcular_cuenta([dic,nov])
        self.assertEqual(cuenta[1]['pagado_directo'],140000000)
        self.assertEqual(cuenta[1]['a_favor_generado'],442150)
        self.assertEqual(cuenta[1]['saldo'],0)
        self.assertEqual(cuenta[2]['credito_aplicado'],442150)
        self.assertEqual(cuenta[2]['saldo'],139115700)
        self.assertEqual(cuenta[2]['pagado_directo'],0)
        self.assertEqual(len(nov.pagos),2)
        self.assertEqual(len(dic.pagos),0)

    def test_credito_sin_periodo_siguiente_se_conserva(self):
        nov=ob(1,11,[140000000])
        self.assertEqual(calcular_cuenta([nov])[1]['a_favor_trasladado'],442150)
        self.assertEqual(calcular_cuenta([nov,ob(2,12)])[2]['credito_aplicado'],442150)

    def test_excedente_cubre_varios_periodos_sin_duplicar_dinero(self):
        filas=[ob(1,9,[35000],importe=10000),ob(2,10,importe=10000),ob(3,11,importe=10000),ob(4,12,importe=10000)]
        c=calcular_cuenta(filas)
        self.assertEqual([c[i]['saldo'] for i in range(1,5)],[0,0,0,5000])
        self.assertEqual(sum(x['credito_aplicado'] for x in c.values()),25000)
        self.assertEqual(c[4]['a_favor_trasladado'],0)

    def test_anulacion_reabre_saldos_derivados(self):
        nov=ob(1,11,[140000000]);dic=ob(2,12,[139115700])
        self.assertEqual(calcular_cuenta([nov,dic])[2]['saldo'],0)
        nov.pagos[0].anulado=True
        c=calcular_cuenta([nov,dic])
        self.assertEqual(c[1]['saldo'],139557850)
        self.assertEqual(c[2]['saldo'],442150)

    def test_credito_no_cruza_organizacion_o_concepto(self):
        c=calcular_cuenta([ob(1,11,[140000000]),ob(2,12,costo=11),ob(3,12,org=8)])
        self.assertEqual(c[2]['credito_aplicado'],0)
        self.assertEqual(c[3]['credito_aplicado'],0)

    def test_no_paga_deudas_anteriores_desde_mes_futuro(self):
        c=calcular_cuenta([ob(1,11),ob(2,12,[150000000])])
        self.assertEqual(c[1]['saldo'],139557850)

    def test_obligacion_anulada_no_consume_credito(self):
        c=calcular_cuenta([ob(1,9,[15000],importe=10000),ob(2,10,importe=10000,estado='anulada'),ob(3,11,importe=10000)])
        self.assertEqual(c[2]['credito_aplicado'],0)
        self.assertEqual(c[3]['saldo'],5000)

    def test_ajuste_de_importe_recalcula_cuenta(self):
        nov=ob(1,11,[140000000]);dic=ob(2,12)
        antes=calcular_cuenta([nov,dic])
        nov.importe_centavos=140000000
        despues=calcular_cuenta([nov,dic])
        self.assertEqual(antes[2]['saldo'],139115700)
        self.assertEqual(despues[2]['saldo'],139557850)

    def test_pago_real_mayor_al_saldo_se_acepta(self):
        item=DTO(id=1,organizacion_id=7,costo_fijo=DTO(organizacion_id=7),importe_centavos=139557850,
            estado='parcial',pagos=[DTO(importe_centavos=110000000,anulado=False)])
        class Pago:
            def __init__(self,obligacion,**valores):
                self.obligacion=obligacion;self.anulado=False
                self.__dict__.update(valores);obligacion.pagos.append(self)
        sesion=DTO(add=lambda p:None,flush=lambda:None,commit=lambda:None)
        registrar_pago(item,organizacion_id=7,fecha_pago='2026-11-06',importe_centavos=30000000,
            medio_pago='transferencia',referencia=None,comprobante=None,observacion=None,usuario_id=1,
            PagoObligacionCostoProductivo=Pago,db_session=sesion)
        self.assertEqual(sum(p.importe_centavos for p in item.pagos),140000000)
        self.assertEqual(item.estado,'pagada')
        anular_pago(item.pagos[-1],organizacion_id=7,motivo='Prueba',usuario_id=1,db_session=sesion,ahora_fn=lambda:None)
        self.assertEqual(saldo_obligacion(item),29557850)
        self.assertEqual(item.estado,'parcial')

    def test_calculo_idempotente_no_modifica_pagos(self):
        filas=[ob(1,11,[140000000]),ob(2,12)]
        self.assertEqual(calcular_cuenta(filas),calcular_cuenta(filas))
        self.assertEqual(len(filas[0].pagos),1)
