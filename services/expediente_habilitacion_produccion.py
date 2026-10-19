"""Expediente consolidado de preparacion productiva, nunca habilitante."""

import hashlib
import io
import json
from decimal import Decimal

from services.avances_produccion import resumir_orden
from services.calidad_produccion import evidencia_calidad
from services.costeo_resultado_produccion import costear_resultado
from services.plan_capacidad_produccion import planificar_capacidad
from services.plan_materiales_produccion import planificar_materiales
from services.propuestas_inventario_produccion import preparar_propuesta_inventario


def construir_expediente(
    *, organizacion_id, unidad_negocio_id, ordenes, mapeos_insumo,
    existencias_producto, versiones_empleado, versiones_maquina, lotes, destinos_por_orden=None,
):
    materiales = planificar_materiales(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        ordenes=ordenes, mapeos_insumo=mapeos_insumo,
    )
    capacidad = planificar_capacidad(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        ordenes=ordenes, versiones_empleado=versiones_empleado,
        versiones_maquina=versiones_maquina,
    )
    calidad = evidencia_calidad(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, lotes=lotes,
    )
    ordenes_controladas = []
    hallazgos = []
    consumos_acumulados = {}
    disponibilidad_original = {}
    disponibilidad_compartida = []
    for orden in sorted(ordenes, key=lambda item: int(item.id)):
        if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "orden_fuera_contexto", "orden_id": orden.id})
            continue
        if orden.estado not in ("en_revision", "aprobada"):
            continue
        avance = resumir_orden(orden)
        item = {
            "orden_id": orden.id, "numero": orden.numero, "estado": orden.estado,
            "tiene_avance": avance["informadas"] > 0, "inventario_aprobado": None,
            "costeo_aprobado": None, "huella_inventario": None, "huella_costeo": None,
        }
        if orden.estado == "aprobada" and avance["informadas"] > 0:
            propuesta = preparar_propuesta_inventario(
                orden, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
                mapeos_insumo=mapeos_insumo,
                destino_existencia_id=(destinos_por_orden or {}).get(orden.id),
                existencias_producto=[x for x in existencias_producto if int(x.producto_id) == int(orden.producto_id)],
            )
            costeo = costear_resultado(
                orden, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
            )
            item.update({
                "inventario_aprobado": propuesta["aprobada"],
                "costeo_aprobado": costeo["aprobado"],
                "huella_inventario": propuesta["huella_propuesta"],
                "huella_costeo": costeo["huella_costeo"],
            })
            for movimiento in propuesta.get("movimientos_propuestos", []):
                if movimiento["tipo"] != "salida_teorica": continue
                existencia_id = movimiento["existencia_sucursal_id"]
                previa = consumos_acumulados.get(existencia_id, Decimal("0"))
                requerida = Decimal(movimiento["cantidad"])
                neta = disponibilidad_original.setdefault(existencia_id, Decimal(movimiento["disponible_antes"]))
                falta = max(Decimal("0"), previa + requerida - neta)
                consumos_acumulados[existencia_id] = previa + requerida
                disponibilidad_compartida.append({"orden_id":orden.id,
                    "existencia_sucursal_id":existencia_id,
                    "unidad_inventario":movimiento["unidad_inventario"],
                    "factor_inventario":movimiento["factor_inventario"],
                    "unidad_medida":movimiento["unidad_medida"],
                    "consumo_acumulado":format(previa+requerida,"f"),
                    "disponible":format(neta,"f"),"faltante":format(falta,"f")})
                if falta:
                    item["inventario_aprobado"] = False
                    hallazgos.append({"codigo":"stock_compartido_insuficiente",
                        "orden_id":orden.id,"existencia_sucursal_id":existencia_id})
            if not item["inventario_aprobado"]:
                hallazgos.append({"codigo": "inventario_no_apto", "orden_id": orden.id})
            if not costeo["aprobado"]:
                hallazgos.append({"codigo": "costeo_no_apto", "orden_id": orden.id})
        ordenes_controladas.append(item)
    componentes = {
        "materiales": {"aprobado": materiales["aprobado"], "huella": materiales["huella_plan"]},
        "capacidad": {"aprobado": capacidad["aprobado"], "huella": capacidad["huella_capacidad"]},
        "calidad": {"aprobado": calidad["aprobado"], "huella": calidad["huella_calidad"]},
    }
    for nombre, componente in componentes.items():
        if not componente["aprobado"]:
            hallazgos.append({"codigo": f"{nombre}_no_apto"})
    apto = not hallazgos and bool(ordenes_controladas)
    resultado = {
        "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "modo": "expediente_no_habilitante", "apto_para_ensayo": apto,
        "habilitacion_ejecucion": False, "componentes": componentes,
        "ordenes": ordenes_controladas, "hallazgos": hallazgos,
        "disponibilidad_compartida": disponibilidad_compartida,
        "controles": {"persistencia": False, "ordenes_iniciadas": 0, "cierres_ejecutados": 0,
                      "movimientos_stock": 0, "costos_modificados": 0, "conexiones_externas": 0},
    }
    resultado["huella_expediente"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_expediente(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
