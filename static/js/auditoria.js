document.querySelectorAll(".auditoria-desplegar").forEach((boton) => {
    boton.addEventListener("click", () => {
        const detalle = document.getElementById(boton.getAttribute("aria-controls"));
        const desplegado = boton.getAttribute("aria-expanded") === "true";
        const etiqueta = boton.dataset.detalle || "cambios";
        boton.setAttribute("aria-expanded", String(!desplegado));
        boton.textContent = `${desplegado ? "Ver" : "Ocultar"} ${etiqueta}`;
        boton.setAttribute(
            "aria-label",
            boton.getAttribute("aria-label").replace(
                `${desplegado ? "Ocultar" : "Ver"} ${etiqueta}`,
                `${desplegado ? "Ver" : "Ocultar"} ${etiqueta}`,
            ),
        );
        detalle.hidden = desplegado;
    });
});
