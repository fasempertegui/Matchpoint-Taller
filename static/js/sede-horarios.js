document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-horarios]");
    if (!formulario) return;

    var dias = Array.from(formulario.querySelectorAll("[name='dias']"));
    var segundaFranja = formulario.querySelector("[name='segunda_franja']");
    var horarioSegundaFranja = formulario.querySelector("[data-segunda-franja]");
    var aplicar = formulario.querySelector("[data-aplicar-horarios]");

    function actualizarDias() {
        var cantidad = dias.filter(function (dia) { return dia.checked; }).length;
        aplicar.textContent = cantidad ? "Aplicar a " + cantidad + (cantidad === 1 ? " día" : " días") : "Aplicar horarios";
    }

    function actualizarSegundaFranja() {
        horarioSegundaFranja.disabled = !segundaFranja.checked;
    }

    formulario.querySelector("[data-atajos-dias]").hidden = false;
    formulario.querySelectorAll("[data-dias]").forEach(function (boton) {
        boton.addEventListener("click", function () {
            var seleccionados = boton.dataset.dias.split(",");
            dias.forEach(function (dia) { dia.checked = seleccionados.includes(dia.value); });
            actualizarDias();
        });
    });
    dias.forEach(function (dia) { dia.addEventListener("change", actualizarDias); });
    segundaFranja.addEventListener("change", actualizarSegundaFranja);
    actualizarDias();
    actualizarSegundaFranja();
});
