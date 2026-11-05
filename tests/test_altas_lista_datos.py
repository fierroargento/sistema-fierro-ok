"""Validación pura de metadatos de altas desde listas de proveedores."""
import unittest
from services.altas_lista_proveedor import datos, unidad


class AltasListaDatosTests(unittest.TestCase):
    def base(self):
        return dict(codigo_proveedor='00000542000020',descripcion='Pintura negra microtexturada',unidad_medida='kg',tipo='consumible')

    def test_pintura_tiene_identidad_unidad_y_tipo(self):
        d=datos(self.base(),4)
        self.assertEqual(d['nombre'],'Pintura negra microtexturada')
        self.assertEqual(d['unidad_medida'],'kg')
        self.assertEqual(d['tipo'],'consumible')
        self.assertEqual(d,datos(self.base(),4))
        self.assertNotEqual(d['codigo'],datos(self.base(),5)['codigo'])

    def test_codigo_interno_no_pierde_ceros(self):
        self.assertEqual(datos(self.base()|{'sku':'0000123'},4)['codigo'],'0000123')

    def test_faltantes_y_limites_rechazados(self):
        for campo,valor in [('codigo_proveedor',''),('descripcion',''),('unidad_medida',''),('tipo','simple'),('sku','x'*81),('descripcion','x'*201)]:
            with self.subTest(campo=campo),self.assertRaises(ValueError):
                datos(self.base()|{campo:valor},4)

    def test_unidades_equivalentes(self):
        for entrada,salida in [('Kilogramos','kg'),('metros','metro'),('m²','m2'),('unidades','unidad')]:
            self.assertEqual(unidad(entrada),salida)

    def test_informa_todos_los_faltantes_juntos(self):
        from services.altas_lista_proveedor import errores_entrada
        errores=errores_entrada({},4)
        self.assertEqual(len(errores),7)
        self.assertTrue(any('Descripción' in e for e in errores))
        self.assertTrue(any('Moneda' in e for e in errores))
        self.assertTrue(any('Cotización' in e for e in errores))
        self.assertEqual(errores_entrada(self.base()|{'precio_proveedor':'100','base_precio':'unitario','moneda_proveedor':'ARS'},4),[])
