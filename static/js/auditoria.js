document.querySelectorAll(".auditoria-desplegar").forEach((boton) => {
    boton.addEventListener("click", () => {
        const detalle = document.getElementById(boton.getAttribute("aria-controls"));
        const desplegado = boton.getAttribute("aria-expanded") === "true";
        boton.setAttribute("aria-expanded", String(!desplegado));
        boton.textContent = desplegado ? "Ver cambios" : "Ocultar cambios";
        boton.setAttribute(
            "aria-label",
            boton.getAttribute("aria-label").replace(
                desplegado ? "Ocultar cambios" : "Ver cambios",
                desplegado ? "Ver cambios" : "Ocultar cambios",
            ),
        );
        detalle.hidden = desplegado;
    });
});
