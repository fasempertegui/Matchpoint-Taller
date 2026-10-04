document.addEventListener("DOMContentLoaded", () => {
    const formulario = document.querySelector("[data-reserva-filtros]");
    if (!formulario) return;

    const sede = formulario.elements.namedItem("sede");
    const cancha = formulario.elements.namedItem("cancha");
    const opciones = Array.from(cancha.options, opcion => opcion.cloneNode(true));

    const actualizarCanchas = () => {
        const seleccionada = cancha.value;
        const disponibles = opciones.filter(opcion => !opcion.value || opcion.dataset.sede === sede.value);
        cancha.replaceChildren(...disponibles.map(opcion => opcion.cloneNode(true)));
        cancha.value = disponibles.some(opcion => opcion.value === seleccionada) ? seleccionada : "";
        cancha.disabled = !sede.value;
    };

    sede.addEventListener("change", actualizarCanchas);
    actualizarCanchas();
});
