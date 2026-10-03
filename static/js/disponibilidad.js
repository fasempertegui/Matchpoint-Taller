document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-disponibilidad]");
    if (!formulario) return;

    var sede = formulario.querySelector("[name='sede']");
    var cancha = formulario.querySelector("[name='cancha']");
    var opciones = Array.from(cancha.options);

    function actualizarCanchas() {
        var canchaSeleccionada = cancha.value;
        cancha.replaceChildren();
        opciones.forEach(function (opcion) {
            if (!opcion.value || opcion.dataset.sede === sede.value) {
                cancha.appendChild(opcion.cloneNode(true));
            }
        });
        cancha.value = Array.from(cancha.options).some(function (opcion) {
            return opcion.value === canchaSeleccionada;
        }) ? canchaSeleccionada : "";
        cancha.disabled = !sede.value;
    }

    sede.addEventListener("change", actualizarCanchas);
    actualizarCanchas();
});
