from decimal import Decimal
import unittest
from services.pintura_producto import calcular


def pieza(cantidad, largo):
    return {'cantidad':str(cantidad),'largo_cm':str(largo),'modo':'longitud'}


class PinturaTests(unittest.TestCase):
    def test_pph3_caras_cantos_extremos_y_consumo(self):
        area, kg, rendimiento = calcular({}, [(pieza(3,18),'BARRA PLANCHUELA 3/4X 1/8'),
                                             (pieza(1,'44.5'),'BARRA PLANCHUELA 1X 1/8'),
                                             ({'modo':'directo'},'TORNILLO MADERA NEGRO N°8'),
                                             ({'modo':'directo'},'TARUGO SIN TOPE 8')])
        assert abs(area-Decimal('0.05')) < Decimal('0.0001')
        assert kg == Decimal('0.004996')
        assert rendimiento == 10
        assert (kg*10900).quantize(Decimal('0.01')) == Decimal('54.46')


    def test_superficie_manual_para_geometria_no_disponible(self):
        assert calcular({'superficie_manual_m2':'0,25'}, [({},'CHAPA')])[1] == Decimal('0.025000')
        with unittest.TestCase().assertRaisesRegex(ValueError,'Faltan medidas'):
            calcular({},[({'modo':'rendimiento'},'CHAPA')])


    def test_rendimiento_invalido_no_se_toma_como_cero(self):
        for valor in ['0','-1','NaN','Infinity','abc']:
            with unittest.TestCase().assertRaises(ValueError):
                calcular({'rendimiento_m2_kg':valor,'superficie_manual_m2':'1'},[])


    def test_redondo_y_longitud_modificada(self):
        p=pieza(1,100)
        a, kg, _ = calcular({},[(p,'BARRA HIERRO TORSIONADO DN 10 MM')])
        assert Decimal('0.031')<a<Decimal('0.032')
        assert calcular({},[(pieza(2,100),'BARRA HIERRO TORSIONADO DN 10 MM')])[1] == (2*a/10).quantize(Decimal('0.000001'))


    def test_material_desconocido_no_se_omite(self):
        with unittest.TestCase().assertRaisesRegex(ValueError,'Faltan medidas'):
            calcular({},[(pieza(1,100),'CAÑO 20X20')])

    def test_no_interpreta_milimetros_como_pulgadas(self):
        with self.assertRaisesRegex(ValueError, 'Faltan medidas'):
            calcular({}, [(pieza(1, 100), 'BARRA PLANCHUELA 20X3 MM')])
