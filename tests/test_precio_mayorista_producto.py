import unittest
from types import SimpleNamespace as Obj
from services.precio_mayorista_producto import calcular_mayorista, calcular_desde_ficha, preparar_mayoristas
from services.motor_comercial_canal import calcular_precio_minimo_canal


class MayoristaTest(unittest.TestCase):
    def precio(self, costo=1063427, **cambios):
        return calcular_mayorista(costo, **dict(dict(utilidad_pct=90,
            utilidad_base='costo', iva_pct=0, iibb_pct=0), **cambios))

    def test_brasero_y_utilidad_individual(self):
        self.assertEqual(self.precio()['base_centavos'], 2020511)
        self.assertEqual(self.precio(utilidad_pct=200)['base_centavos'], 3190281)

    def test_margen_sobre_venta(self):
        self.assertEqual(self.precio(10000, utilidad_base='precio_venta', utilidad_pct=40)['base_centavos'],16667)

    def test_impuestos_separados_sin_duplicar_utilidad(self):
        p=self.precio(10000, utilidad_pct=90, iva_pct=21, iibb_pct=4)
        self.assertEqual((p['base_centavos'],p['neto_centavos'],p['precio_final_centavos']), (19000,19792,23948))

    def test_cero_explicito_no_es_dato_faltante(self):
        self.assertEqual(self.precio(10000, utilidad_pct=0)['precio_final_centavos'],10000)
        for campo in ('utilidad_pct','iva_pct','iibb_pct'):
            with self.subTest(campo=campo), self.assertRaises(ValueError): self.precio(**{campo:None})

    def test_valores_invalidos(self):
        for cambios in ({'utilidad_pct':'NaN'}, {'utilidad_pct':-1},
                {'utilidad_base':'precio_venta','utilidad_pct':100},
                {'utilidad_base':'general'}, {'iibb_pct':100}, {'iva_pct':101}):
            with self.subTest(cambios=cambios), self.assertRaises(ValueError): self.precio(**cambios)

    def test_aislamiento_ficha(self):
        c=Obj(producto_id=1, organizacion_id=2, costo_total_centavos=10000)
        for ficha in (None,Obj(producto_id=1,organizacion_id=3),Obj(producto_id=4,organizacion_id=2)):
            with self.assertRaises(ValueError): calcular_desde_ficha(c,ficha)

    def test_canal_cubre_gastos_sobre_mayorista(self):
        base=self.precio(10000)['precio_final_centavos']
        canal=Obj(incremento_redondeo_centavos=1,comision_pct=20,publicidad_pct=0,
            financiacion_pct=0,devoluciones_pct=0, umbral_envio_centavos=0,
            costo_envio_default_centavos=0,tramos=[Obj(precio_desde_centavos=0,
                precio_hasta_centavos=None,cargo_fijo_centavos=0)])
        p=calcular_precio_minimo_canal(base,canal)
        self.assertEqual(p['precio_final_centavos'],23750)
        self.assertEqual(p['liquidacion_centavos'],base)

    def test_preview_ultima_version_y_faltantes(self):
        a=Obj(id=1,numero_version=1,producto_id=1,organizacion_id=2,moneda='ARS',
            costo_total_centavos=10000,producto=Obj(sku='A'))
        b=Obj(**{**vars(a),'id':2,'numero_version':2,'costo_total_centavos':20000})
        f=Obj(producto_id=1,organizacion_id=2,utilidad_pct=90,utilidad_base='costo',iva_pct=0,iibb_pct=0)
        filas=preparar_mayoristas([a,b],{1:f})
        self.assertEqual(len(filas),1)
        self.assertEqual(filas[0]['precio']['base_centavos'],38000)
        self.assertIsNotNone(preparar_mayoristas([a],{})[0]['error'])

if __name__=='__main__': unittest.main()
