document.addEventListener("DOMContentLoaded", function () {
    var filtros = document.querySelector("[data-planilla-filtros]");
    if (filtros) {
        filtros.addEventListener("change", function (evento) {
            if (evento.target.name === "sede") filtros.elements.cancha.disabled = true;
            filtros.requestSubmit();
        });
    }

    var tabla = document.querySelector(".planilla-tabla");
    var barra = document.querySelector("[data-planilla-seleccion]");
    if (!tabla || !barra) return;
    var celdas = Array.from(tabla.querySelectorAll("[data-seleccionar-turno]"));
    var seleccion = new Set();
    var arrastre = null;
    var omitirClick = false;

    function actualizar() {
        celdas.forEach(function (celda) {
            var elegida = seleccion.has(celda.dataset.seleccionarTurno);
            celda.classList.toggle("planilla-celda-seleccionada", elegida);
            celda.setAttribute("aria-pressed", String(elegida));
        });
        barra.hidden = seleccion.size === 0;
        barra.querySelector("[data-seleccion-cantidad]").textContent = seleccion.size === 1
            ? "1 turno seleccionado" : seleccion.size + " turnos seleccionados";
        var valores = barra.querySelector("[data-seleccion-valores]");
        valores.replaceChildren();
        Array.from(seleccion).sort(function (a, b) {
            var inicio = a.split("-").map(Number);
            var fin = b.split("-").map(Number);
            return inicio[0] - fin[0] || inicio[1] - fin[1];
        }).forEach(function (valor) {
            var entrada = document.createElement("input");
            entrada.type = "hidden";
            entrada.name = "turno";
            entrada.value = valor;
            valores.append(entrada);
        });
        document.body.classList.toggle("planilla-con-seleccion", seleccion.size > 0);
    }

    function alternar(celda) {
        var valor = celda.dataset.seleccionarTurno;
        if (seleccion.has(valor)) seleccion.delete(valor);
        else seleccion.add(valor);
        actualizar();
    }

    tabla.addEventListener("click", function (evento) {
        if (omitirClick) {
            evento.preventDefault();
            return;
        }
        var celda = evento.target.closest("[data-seleccionar-turno]");
        if (celda) {
            if (evento.detail === 0) alternar(celda);
            return;
        }
        var hora = evento.target.closest("[data-seleccionar-hora]");
        if (hora) {
            celdas.forEach(function (vacia) {
                if (vacia.closest("td").dataset.hora === hora.dataset.seleccionarHora) {
                    seleccion.add(vacia.dataset.seleccionarTurno);
                }
            });
            actualizar();
        }
    });

    tabla.addEventListener("pointerdown", function (evento) {
        var celda = evento.target.closest("[data-seleccionar-turno]");
        if (!celda || evento.button !== 0 || !evento.isPrimary) return;
        evento.preventDefault();
        celda.focus();
        var posicion = celda.closest("td");
        arrastre = {
            pointerId: evento.pointerId, celda: celda,
            dia: Number(posicion.dataset.dia), hora: Number(posicion.dataset.hora),
            inicial: new Set(seleccion), movido: false,
        };
    });

    document.addEventListener("pointermove", function (evento) {
        if (!arrastre || evento.pointerId !== arrastre.pointerId) return;
        var destino = document.elementFromPoint(evento.clientX, evento.clientY);
        var posicion = destino && destino.closest("td[data-dia][data-hora]");
        if (!posicion || !tabla.contains(posicion)) return;
        var dia = Number(posicion.dataset.dia);
        var hora = Number(posicion.dataset.hora);
        if (dia === arrastre.dia && hora === arrastre.hora && !arrastre.movido) return;
        arrastre.movido = true;
        seleccion = new Set(arrastre.inicial);
        celdas.forEach(function (celda) {
            var ubicacion = celda.closest("td");
            var diaCelda = Number(ubicacion.dataset.dia);
            var horaCelda = Number(ubicacion.dataset.hora);
            if (diaCelda >= Math.min(dia, arrastre.dia) && diaCelda <= Math.max(dia, arrastre.dia)
                && horaCelda >= Math.min(hora, arrastre.hora) && horaCelda <= Math.max(hora, arrastre.hora)) {
                seleccion.add(celda.dataset.seleccionarTurno);
            }
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
        arrastre = null;
        actualizar();
    });

    barra.querySelector("[data-limpiar-seleccion]").addEventListener("click", function () {
        seleccion.clear();
        actualizar();
        if (celdas.length) celdas[0].focus();
    });
    barra.addEventListener("submit", function (evento) {
        if (seleccion.size === 0) evento.preventDefault();
    });
});
