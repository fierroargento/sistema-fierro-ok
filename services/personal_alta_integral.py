"""Alta administrativa con sueldo y horario opcionales, en una sola transacción."""
from services.personal_legajo import guardar_salario, guardar_horario


def completar_alta(e, form, *, modelos, db_session, usuario_id):
    if form.get('accion') != 'crear':
        if form.get('cargar_sueldo_inicial')=='1' or form.get('cargar_horario_inicial')=='1':
            raise ValueError('Actualizá el sueldo y los horarios desde las secciones del legajo existente.')
        return
    if form.get('cargar_sueldo_inicial')=='1':
        campos=('sueldo_base','adicionales','otros_costos','porcentaje_cargas','horas_mensuales','horas_productivas','ubicacion_trabajo','tipo_funcion','porcentaje_productivo')
        salario={c:form.get('inicial_'+c) for c in campos}
        salario['version_actual']=''
        guardar_salario(e,salario,modelos=modelos,db_session=db_session,usuario_id=usuario_id)
    if form.get('cargar_horario_inicial')=='1':
        dias=form.getlist('inicial_dias') if hasattr(form,'getlist') else form.get('inicial_dias',[])
        if isinstance(dias,str):dias=[dias]
        if not dias or len(dias)>7 or len(set(dias))!=len(dias):raise ValueError('Elegí los días del horario laboral, sin repetirlos.')
        horario={c:form.get('inicial_'+c) for c in ('entrada','salida','nocturno','pausa_minutos','desde','hasta')}
        for dia in dias:guardar_horario(e,horario|{'dia_semana':dia},db_session)
