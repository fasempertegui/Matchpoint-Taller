window.prepararCamposOperacion = function () {
    var formulario = document.querySelector("[data-agenda-operacion]");
    if (!formulario || formulario.dataset.camposPreparados) return;
    formulario.dataset.camposPreparados = "1";

    formulario.querySelectorAll("[data-operacion-refinamiento]").forEach(function (selector) {
        var bloque = document.getElementById(selector.getAttribute("aria-controls"));

        function actualizarRefinamiento() {
            var abierto = selector.value === "seleccionar";
            bloque.hidden = !abierto;
            bloque.disabled = !abierto;
            if (!abierto) {
                bloque.querySelectorAll("input").forEach(function (campo) {
                    if (campo.type === "checkbox") campo.checked = false;
                    else campo.value = "";
                });
            }
        }

        selector.value = bloque.hasAttribute("data-refinamiento-abierto") ? "seleccionar" : "todo";
        actualizarRefinamiento();
        selector.addEventListener("change", actualizarRefinamiento);
    });

    if (formulario.elements.fecha_desde) {
        formulario.addEventListener("formdata", function (evento) {
            ["fecha_desde", "fecha_hasta"].forEach(function (nombre) {
                if (evento.formData.get(nombre) === "") evento.formData.delete(nombre);
            });
        });
    }

    var entradasSede = formulario.querySelectorAll('input[name="sedes"]');
    var opcionesCancha = formulario.querySelectorAll("[data-sede-cancha]");
    var horario = formulario.elements.horario;
    var horasPorSede = JSON.parse(horario.dataset.horasPorSede);

    function formatearHora(hora) {
        return String(hora).padStart(2, "0") + ":00";
    }

    function actualizarCampos() {
        var bloquear = formulario.elements.operacion.value === "bloquear";
        var variasSedes = formulario.elements.seleccion_sedes.value === "seleccionar";
        var variasCanchas = formulario.elements.seleccion_canchas.value === "seleccionar";
        formulario.querySelector("[data-operacion-varias-sedes]").hidden = !variasSedes;
        var sedesElegidas = new Set();
        entradasSede.forEach(function (sede) {
            sede.disabled = !variasSedes;
            if (!variasSedes || sede.checked) sedesElegidas.add(sede.value);
        });
        formulario.querySelector("[data-operacion-varias-canchas]").hidden = !variasCanchas;
        opcionesCancha.forEach(function (opcion) {
            var coincide = sedesElegidas.has(opcion.dataset.sedeCancha);
            opcion.hidden = !coincide;
            opcion.querySelector("input").disabled = !variasCanchas || !coincide;
        });

        var horas = [...new Set([...sedesElegidas].flatMap(function (sede) {
            return horasPorSede[sede] || [];
        }))].sort(function (a, b) { return a - b; });
        var inicioElegido = horario.value;
        horario.replaceChildren(
            new Option("Día completo", "dia"),
            ...horas.map(function (hora) {
                var desde = formatearHora(hora);
                return new Option("Desde las " + desde, desde, false, desde === inicioElegido);
            })
        );
        var desde = horario.value;
        var hasta = formulario.elements.hora_hasta;
        var finElegido = hasta.value;
        hasta.replaceChildren(
            new Option("Fin del día", ""),
            ...horas.map(function (hora) { return formatearHora(hora + 1); })
                .filter(function (fin) { return desde !== "dia" && fin > desde; })
                .map(function (fin) { return new Option(fin, fin, false, fin === finElegido); })
        );
        hasta.disabled = desde === "dia";
        formulario.querySelector("[data-operacion-hasta]").hidden = desde === "dia";
        if (formulario.elements.motivo_bloqueo) {
            formulario.querySelector("[data-operacion-motivo-bloqueo]").hidden = !bloquear;
            formulario.elements.motivo_bloqueo.disabled = !bloquear;
            formulario.elements.motivo_bloqueo.required = bloquear;
            formulario.querySelector("[data-operacion-observaciones]").hidden = !bloquear;
            formulario.elements.observaciones.disabled = !bloquear;
        }
        formulario.querySelector("[data-operacion-motivo-anulacion]").hidden = bloquear;
        formulario.elements.motivo_anulacion.disabled = bloquear;
        var opcionBloqueos = formulario.querySelector("[data-operacion-actividad-bloqueo]");
        if (opcionBloqueos) {
            opcionBloqueos.hidden = bloquear;
            opcionBloqueos.querySelector("input").disabled = bloquear;
        }
    }

    formulario.addEventListener("change", actualizarCampos);
    actualizarCampos();
};

document.addEventListener("DOMContentLoaded", window.prepararCamposOperacion);
