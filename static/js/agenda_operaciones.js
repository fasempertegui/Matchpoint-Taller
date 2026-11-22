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

    function actualizarCampos() {
        var bloquear = formulario.elements.operacion.value === "bloquear";
        var variasCanchas = formulario.elements.seleccion_canchas.value === "seleccionar";
        formulario.querySelector("[data-operacion-varias-canchas]").hidden = !variasCanchas;
        formulario.querySelectorAll('input[name="canchas"]').forEach(function (cancha) {
            cancha.disabled = !variasCanchas;
        });
        var desde = formulario.elements.horario.value;
        var hasta = formulario.elements.hora_hasta;
        var finElegido = hasta.value;
        var opciones = [new Option("Fin del día", "")];
        if (desde !== "dia") {
            hasta.dataset.finalesHabilitados.split(",").forEach(function (valor) {
                if (valor && valor > desde) opciones.push(new Option(valor, valor, false, valor === finElegido));
            });
        }
        hasta.replaceChildren(...opciones);
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
