function ajustarAyudaContextual(evento) {
    const ayuda = evento.target.closest(".ayuda-contextual");
    if (!ayuda || ayuda.contains(evento.relatedTarget)) return;

    const texto = ayuda.querySelector(".ayuda-contextual-texto");
    if (!texto) return;

    texto.style.removeProperty("transform");
    const bordeDerecho = document.documentElement.clientWidth - 8;
    const desborde = texto.getBoundingClientRect().right - bordeDerecho;
    if (desborde > 0) texto.style.transform = `translateX(-${desborde}px)`;
}

document.addEventListener("pointerover", ajustarAyudaContextual);
document.addEventListener("focusin", ajustarAyudaContextual);
