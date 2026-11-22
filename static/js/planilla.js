document.addEventListener("DOMContentLoaded", function () {
    var filtros = document.querySelector("[data-planilla-filtros]");
    if (filtros) {
        filtros.addEventListener("change", function (evento) {
            if (evento.target.name === "sede") filtros.elements.cancha.disabled = true;
        });
    }

    var tabla = document.querySelector(".planilla-tabla");
    var barra = document.querySelector("[data-planilla-seleccion]");
    if (!tabla || !barra) return;
    var celdas = Array.from(tabla.querySelectorAll("[data-seleccionar-turno]"));
    var porCoordenada = new Map(celdas.map(function (celda) { return [celda.dataset.seleccionarTurno, celda]; }));
    var aviso = document.querySelector("[data-planilla-aviso]");
    var crear = barra.querySelector("[data-crear-horarios]");
    var quitar = barra.querySelector("[data-quitar-horarios]");
    var formularioQuitar = document.querySelector("[data-quitar-formulario]");
    var detalle = barra.querySelector("[data-ver-horario]");
    var accionesPersonas = barra.querySelectorAll("[data-gestionar-personas]");
    var menusPersonas = Array.from(barra.querySelectorAll("[data-menu-personas]"));
    var funcionPersonas = barra.querySelector("[data-funcion-personas]");

    function cerrarMenus(excepto) {
        menusPersonas.forEach(function (menu) { if (menu !== excepto) menu.open = false; });
    }
    menusPersonas.forEach(function (menu) {
        menu.addEventListener("toggle", function () {
            menu.querySelector("summary").setAttribute("aria-expanded", String(menu.open));
            if (menu.open) cerrarMenus(menu);
        });
    });
    document.addEventListener("click", function (evento) {
        menusPersonas.forEach(function (menu) { if (!menu.contains(evento.target)) menu.open = false; });
    });
    document.addEventListener("keydown", function (evento) {
        if (evento.key !== "Escape") return;
        var abierto = menusPersonas.find(function (menu) { return menu.open; });
        if (abierto) {
            evento.preventDefault();
            cerrarMenus();
            abierto.querySelector("summary").focus();
        }
    });
    var seleccion = new Set();
    var tipo = null;
    var arrastre = null;
    var omitirClick = false;

    function informar(texto) {
        aviso.textContent = texto;
        aviso.hidden = !texto;
    }

    function compatible(celda) {
        return !tipo || celda.dataset.tipoTurno === tipo;
    }

    function actualizar() {
        if (!seleccion.size) tipo = null;
        celdas.forEach(function (celda) {
            var elegida = seleccion.has(celda.dataset.seleccionarTurno);
            celda.classList.toggle("planilla-celda-seleccionada", elegida);
            celda.setAttribute("aria-pressed", String(elegida));
        });
        barra.hidden = seleccion.size === 0;
        barra.querySelector("[data-seleccion-cantidad]").textContent = seleccion.size === 1
            ? "1 horario seleccionado"
            : seleccion.size + " horarios seleccionados";
        crear.hidden = tipo !== "libre";
        crear.disabled = tipo !== "libre";
        quitar.hidden = tipo !== "creado";
        barra.querySelector("[data-separador-quitar]").hidden = tipo !== "creado";
        quitar.disabled = tipo !== "creado";
        var valoresQuitar = formularioQuitar.querySelector("[data-quitar-valores]");
        valoresQuitar.replaceChildren();
        if (tipo === "creado") {
            seleccion.forEach(function (valor) {
                var celda = porCoordenada.get(valor);
                [["turno_id", celda.dataset.turnoId], ["version", celda.dataset.version]].forEach(function (dato) {
                    var entrada = document.createElement("input");
                    entrada.type = "hidden";
                    entrada.name = dato[0];
                    entrada.value = dato[1];
                    valoresQuitar.append(entrada);
                });
            });
        }
        formularioQuitar.dataset.confirmar = (seleccion.size === 1
            ? "Se quitará 1 horario de la planilla"
            : "Se quitarán " + seleccion.size + " horarios de la planilla")
            + " con sus profesores y participantes. Las clases ya generadas se conservan.";
        cerrarMenus();
        menusPersonas.forEach(function (menu) { menu.hidden = tipo !== "creado"; });
        accionesPersonas.forEach(function (boton) {
            boton.hidden = tipo !== "creado";
            boton.disabled = tipo !== "creado";
        });
        detalle.hidden = tipo !== "creado" || seleccion.size !== 1;
        detalle.removeAttribute("href");
        if (!detalle.hidden) detalle.href = porCoordenada.get(seleccion.values().next().value).dataset.urlDetalle;
        var valores = barra.querySelector("[data-seleccion-valores]");
        valores.replaceChildren();
        Array.from(seleccion).sort().forEach(function (valor) {
            var entrada = document.createElement("input");
            entrada.type = "hidden";
            entrada.name = "turno";
            entrada.value = valor;
            valores.append(entrada);
        });
        document.body.classList.toggle("planilla-con-seleccion", seleccion.size > 0);
    }

    function alternar(celda) {
        if (!compatible(celda)) {
            informar("No se pueden mezclar horarios libres y creados. Limpiá la selección para cambiar de tipo.");
            return;
        }
        informar("");
        var valor = celda.dataset.seleccionarTurno;
        if (seleccion.has(valor)) seleccion.delete(valor);
        else {
            tipo = celda.dataset.tipoTurno;
            seleccion.add(valor);
        }
        actualizar();
    }

    tabla.addEventListener("click", function (evento) {
        if (omitirClick) { evento.preventDefault(); return; }
        var celda = evento.target.closest("[data-seleccionar-turno]");
        if (celda) {
            if (evento.detail === 0) alternar(celda);
            return;
        }
        var hora = evento.target.closest("[data-seleccionar-hora]");
        if (!hora) return;
        var fila = celdas.filter(function (item) { return item.closest("td").dataset.hora === hora.dataset.seleccionarHora; });
        var tipos = new Set(fila.map(function (item) { return item.dataset.tipoTurno; }));
        if (!tipo && tipos.size > 1) {
            informar("Seleccioná primero una celda libre o creada para elegir qué horarios sumar de esta fila.");
            return;
        }
        if (!tipo && fila.length) tipo = fila[0].dataset.tipoTurno;
        fila.filter(compatible).forEach(function (item) { seleccion.add(item.dataset.seleccionarTurno); });
        informar("");
        actualizar();
    });

    tabla.addEventListener("pointerdown", function (evento) {
        var celda = evento.target.closest("[data-seleccionar-turno]");
        if (arrastre || !celda || evento.button !== 0 || !evento.isPrimary) return;
        if (!compatible(celda)) {
            informar("No se pueden mezclar horarios libres y creados. Limpiá la selección para cambiar de tipo.");
            return;
        }
        informar("");
        var posicion = celda.closest("td");
        arrastre = {
            pointerId: evento.pointerId, celda: celda,
            dia: Number(posicion.dataset.dia), hora: Number(posicion.dataset.hora),
            ultimaPosicion: posicion,
            inicial: new Set(seleccion), tipoInicial: tipo,
            tipoGesto: celda.dataset.tipoTurno,
            deseleccionando: seleccion.has(celda.dataset.seleccionarTurno),
            movido: false,
        };
    });

    document.addEventListener("pointermove", function (evento) {
        if (!arrastre || evento.pointerId !== arrastre.pointerId) return;
        var destino = document.elementFromPoint(evento.clientX, evento.clientY);
        var posicion = destino && destino.closest("td[data-dia][data-hora]");
        if (!posicion || posicion === arrastre.ultimaPosicion || !tabla.contains(posicion)) return;
        arrastre.ultimaPosicion = posicion;
        arrastre.movido = true;
        var dia = Number(posicion.dataset.dia);
        var hora = Number(posicion.dataset.hora);
        var diaMinimo = Math.min(dia, arrastre.dia);
        var diaMaximo = Math.max(dia, arrastre.dia);
        var horaMinima = Math.min(hora, arrastre.hora);
        var horaMaxima = Math.max(hora, arrastre.hora);
        seleccion = new Set(arrastre.inicial);
        tipo = arrastre.deseleccionando ? arrastre.tipoInicial : arrastre.tipoGesto;
        celdas.forEach(function (celda) {
            if (!arrastre.deseleccionando && !compatible(celda)) return;
            var ubicacion = celda.closest("td");
            var diaCelda = Number(ubicacion.dataset.dia);
            var horaCelda = Number(ubicacion.dataset.hora);
            if (diaCelda < diaMinimo || diaCelda > diaMaximo || horaCelda < horaMinima || horaCelda > horaMaxima) return;
            if (arrastre.deseleccionando) seleccion.delete(celda.dataset.seleccionarTurno);
            else seleccion.add(celda.dataset.seleccionarTurno);
        });
        actualizar();
    });

    document.addEventListener("pointerup", function (evento) {
        if (!arrastre || evento.pointerId !== arrastre.pointerId) return;
        if (!arrastre.movido) alternar(arrastre.celda);
        omitirClick = true;
        window.setTimeout(function () { omitirClick = false; }, 0);
        arrastre = null;
    });

    document.addEventListener("pointercancel", function (evento) {
        if (!arrastre || evento.pointerId !== arrastre.pointerId) return;
        seleccion = arrastre.inicial;
        tipo = arrastre.tipoInicial;
        arrastre = null;
        actualizar();
    });

    barra.querySelector("[data-limpiar-seleccion]").addEventListener("click", function () {
        seleccion.clear();
        informar("");
        actualizar();
        if (celdas.length) celdas[0].focus();
    });
    formularioQuitar.addEventListener("submit", function (evento) {
        if (!seleccion.size || tipo !== "creado") evento.preventDefault();
    });
    barra.addEventListener("submit", function (evento) {
        var gestionaPersonas = evento.submitter && evento.submitter.hasAttribute("data-gestionar-personas");
        if (!seleccion.size || (gestionaPersonas ? tipo !== "creado" : tipo !== "libre")) {
            evento.preventDefault();
            return;
        }
        funcionPersonas.disabled = !gestionaPersonas;
        funcionPersonas.value = gestionaPersonas ? evento.submitter.dataset.funcion : "";
    });
});
