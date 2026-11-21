(function () {
    const selector = "[data-tooltip], .ayuda-contextual-boton";
    const contenedoresSinTooltip = "[inert], dialog:not([open]), .sidebar";
    const texto = document.createElement("div");
    texto.id = "tooltip-compartido";
    texto.setAttribute("role", "tooltip");

    let ancla = null;
    let globo = null;
    let control = null;
    let porTeclado = false;
    let temporizador;
    let cuadro;

    function cerrar() {
        window.clearTimeout(temporizador);
        window.cancelAnimationFrame(cuadro);
        if (!ancla) return;

        globo.classList.remove("tooltip-visible");
        if (globo === texto) {
            texto.remove();
            const referencias = control.getAttribute("aria-describedby")?.split(/\s+/) || [];
            const restantes = referencias.filter(id => id && id !== texto.id);
            if (restantes.length) control.setAttribute("aria-describedby", restantes.join(" "));
            else control.removeAttribute("aria-describedby");
        } else if (ancla.parentNode) {
            ancla.after(globo);
        } else {
            globo.remove();
        }
        ancla = null;
        globo = null;
        control = null;
        porTeclado = false;
    }

    function posicionar() {
        const caja = ancla.getBoundingClientRect();
        const ancho = document.documentElement.clientWidth;
        const alto = document.documentElement.clientHeight;
        if (!caja.width || !caja.height || caja.bottom <= 0 || caja.right <= 0
            || caja.top >= alto || caja.left >= ancho || ancla.closest(contenedoresSinTooltip)
            || control.matches(":disabled")) {
            cerrar();
            return;
        }
        if (globo === texto && texto.textContent !== ancla.dataset.tooltip) {
            texto.textContent = ancla.dataset.tooltip;
        }
        const sidebar = ancla.closest(".sidebar");
        let izquierda;
        let superior;
        if (sidebar) {
            globo.style.removeProperty("max-height");
            izquierda = sidebar.getBoundingClientRect().right + 6 + "px";
            const centrado = caja.top + (caja.height - globo.offsetHeight) / 2;
            superior = Math.max(8, Math.min(centrado, alto - globo.offsetHeight - 8)) + "px";
        } else {
            const debajo = caja.bottom + 6;
            const espacioDebajo = alto - debajo - 8;
            const espacioArriba = caja.top - 14;
            const mostrarDebajo = globo.scrollHeight + 2 <= espacioDebajo || espacioDebajo >= espacioArriba;
            const limite = Math.max(0, mostrarDebajo ? espacioDebajo : espacioArriba) + "px";
            if (globo.style.maxHeight !== limite) globo.style.maxHeight = limite;
            izquierda = Math.max(8, Math.min(caja.left, ancho - globo.offsetWidth - 8)) + "px";
            superior = (mostrarDebajo ? debajo : caja.top - globo.offsetHeight - 6) + "px";
        }
        if (globo.style.left !== izquierda) globo.style.left = izquierda;
        if (globo.style.top !== superior) globo.style.top = superior;
        cuadro = window.requestAnimationFrame(posicionar);
    }

    function abrir(origen, teclado) {
        if (origen.closest(contenedoresSinTooltip)) {
            cerrar();
            return;
        }
        window.clearTimeout(temporizador);
        if (origen === ancla) {
            porTeclado = teclado;
            return;
        }
        cerrar();
        const contenido = origen.hasAttribute("data-tooltip") ? texto : origen.nextElementSibling;
        if (!contenido) return;
        ancla = origen;
        globo = contenido;
        control = origen.control || origen.closest("a[href], button") || origen;
        porTeclado = teclado;

        if (globo === texto) {
            const referencias = control.getAttribute("aria-describedby") || "";
            control.setAttribute("aria-describedby", (referencias + " " + texto.id).trim());
        }
        const contenedor = ancla.closest("dialog[open]") || document.body;
        contenedor.append(globo);
        globo.classList.add("tooltip-visible");
        posicionar();
    }

    function dentro(elemento, destino) {
        return elemento && destino instanceof Node && elemento.contains(destino);
    }

    document.addEventListener("pointerover", function (evento) {
        if (evento.pointerType === "touch") return;
        if (dentro(globo, evento.target)) {
            window.clearTimeout(temporizador);
            return;
        }
        const origen = evento.target.closest(selector);
        if (origen && !dentro(origen, evento.relatedTarget)) abrir(origen, false);
    });
    document.addEventListener("pointerout", function (evento) {
        if (porTeclado || evento.pointerType === "touch") return;
        if (!dentro(ancla, evento.target) && !dentro(globo, evento.target)) return;
        if (dentro(ancla, evento.relatedTarget) || dentro(globo, evento.relatedTarget)) return;
        window.clearTimeout(temporizador);
        if (globo === texto) cerrar();
        else temporizador = window.setTimeout(cerrar, 180);
    });
    document.addEventListener("focusin", function (evento) {
        const destino = evento.target;
        if (destino.matches(":focus-visible")) {
            const origen = destino.closest(selector)
                || (destino.matches("a[href], button") && destino.querySelector("[data-tooltip]"));
            if (origen) {
                abrir(origen, true);
                return;
            }
        }
        if (destino !== control) cerrar();
    });
    document.addEventListener("focusout", function (evento) {
        if (porTeclado && evento.target === control) cerrar();
    });
    document.addEventListener("click", function (evento) {
        if (dentro(globo, evento.target)) return;
        const origen = evento.target.closest(selector);
        if (origen && !origen.hasAttribute("data-tooltip")) abrir(origen, evento.detail === 0);
        else cerrar();
    }, true);
    document.addEventListener("keydown", function (evento) {
        if (evento.key !== "Escape" || !ancla) return;
        cerrar();
        evento.preventDefault();
        evento.stopPropagation();
    }, true);
    document.addEventListener("scroll", function (evento) {
        if (!dentro(globo, evento.target)) cerrar();
    }, true);
    window.addEventListener("blur", cerrar);
    window.addEventListener("pagehide", cerrar);
}());
