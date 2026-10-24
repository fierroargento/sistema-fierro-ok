"""Alta administrativa con sueldo y horario opcionales, en una sola transacción."""
import json
from services.personal_legajo import guardar_salario, guardar_horario


def completar_alta(e, form, *, modelos, db_session, usuario_id):
    if form.get('accion') != 'crear':
        if form.get('cargar_sueldo_inicial')=='1' or form.get('cargar_horario_inicial')=='1':
            raise ValueError('Actualizá el sueldo y los horarios desde las secciones del legajo existente.')
        return
    if form.get('cargar_horario_inicial')=='1':
        if 'inicial_tramos' in form:
            texto = form.get('inicial_tramos') or ''
            if len(texto)>30000:
                raise ValueError('El horario supera el tamaño permitido.')
            try:
                tramos = json.loads(texto)
            except (ValueError, TypeError) as error:
                raise ValueError('Revisá los tramos del horario laboral.') from error
            campos = {'dia_semana','entrada','salida','nocturno','pausa_minutos'}
            if not isinstance(tramos,list) or not 1<=len(tramos)<=42 or any(
                    not isinstance(t,dict) or set(t)!=campos or any(not isinstance(v,str) for v in t.values()) for t in tramos):
                raise ValueError('Agregá entre 1 y 42 tramos con día, entrada, salida y descanso.')
            for tramo in tramos:
                guardar_horario(e,tramo|{'desde':form.get('inicial_desde'),'hasta':form.get('inicial_hasta')},db_session)
        else:
            # Compatibilidad con formularios abiertos antes de esta actualización.
            dias=form.getlist('inicial_dias') if hasattr(form,'getlist') else form.get('inicial_dias',[])
            if isinstance(dias,str):dias=[dias]
            if not dias or len(dias)>7 or len(set(dias))!=len(dias):raise ValueError('Elegí los días del horario laboral, sin repetirlos.')
            horario={c:form.get('inicial_'+c) for c in ('entrada','salida','nocturno','pausa_minutos','desde','hasta')}
            for dia in dias:guardar_horario(e,horario|{'dia_semana':dia},db_session)
    if form.get('cargar_sueldo_inicial')=='1':
        campos=('sueldo_base','adicionales','otros_costos','porcentaje_cargas','horas_mensuales','ubicacion_trabajo','tipo_funcion')
        salario={c:form.get('inicial_'+c) for c in campos}
        salario['version_actual']=''
        guardar_salario(e,salario,modelos=modelos,db_session=db_session,usuario_id=usuario_id)
