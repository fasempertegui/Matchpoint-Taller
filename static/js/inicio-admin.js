document.addEventListener("DOMContentLoaded", function () {
    // Punto indicador interactivo en sparklines
    document.querySelectorAll("[data-sparkline]").forEach(function (svg) {
        var punto = svg.querySelector("[data-spark-punto]");
        if (!punto) return;

        svg.querySelectorAll(".dashboard-spark-zona").forEach(function (zona) {
            zona.addEventListener("pointerenter", function () {
                if (zona.dataset.ultimo === "1") {
                    punto.style.opacity = "0";
                    return;
                }
                punto.setAttribute("cx", zona.dataset.cx);
                punto.setAttribute("cy", zona.dataset.cy);
                punto.style.opacity = "1";
            });
            zona.addEventListener("pointerleave", function () {
                punto.style.opacity = "0";
            });
        });
    });

    // Mapa de calor: Ocupación por día y hora
    var nodoDatos = document.getElementById("dashboard-ocupacion-datos");
    var grid = document.getElementById("dashboard-hm-grid");
    var selectorSede = document.getElementById("dashboard-hm-sede");
    if (!nodoDatos || !grid) return;

    var datos = JSON.parse(nodoDatos.textContent);
    var sedeActual = "todas";
    var tipoActual = "todo";

    function nivelVioleta(pct) {
        if (pct <= 0) return 0;
        if (pct <= 25) return 1;
        if (pct <= 50) return 2;
        if (pct <= 75) return 3;
        return 4;
    }

    function renderHeatmap(animarEntrada = false) {
        var matriz = datos.matrices[sedeActual] || datos.matrices.todas || [];
        var horas = datos.horas || [];
        var dias = datos.dias || [];
        grid.innerHTML = "";

        matriz.forEach(function (fila, dIdx) {
            var esHoy = dIdx === datos.dia_actual;
            var filaEl = document.createElement("div");
            filaEl.className = "dashboard-hm-fila";

            var diaEl = document.createElement("span");
            diaEl.className = "dashboard-hm-dia" + (esHoy ? " dashboard-hm-dia-hoy" : "");
            diaEl.textContent = dias[dIdx] || "";

            var celdasEl = document.createElement("div");
            celdasEl.className = "dashboard-hm-celdas" + (esHoy ? " dashboard-hm-fila-hoy" : "");
            celdasEl.style.gridTemplateColumns = "repeat(" + horas.length + ", minmax(0, 1fr))";
            if (animarEntrada) {
                celdasEl.classList.add("dashboard-hm-entrada");
                celdasEl.style.setProperty("--retraso-entrada", dIdx * 35 + "ms");
            }

            fila.forEach(function (celda, hIdx) {
                var hora = horas[hIdx];
                var horaTxt = String(hora).padStart(2, "0") + ":00";
                var el = document.createElement("div");
                el.setAttribute("tabindex", "0");

                if (celda.cerrada) {
                    el.className = "dashboard-hm-celda dashboard-hm-cerrada";
                    el.dataset.tooltip = dias[dIdx] + " " + horaTxt + " · Sede cerrada";
                } else {
                    var valor = tipoActual === "clases"
                        ? celda.clases
                        : (tipoActual === "reservas" ? celda.reservas : celda.clases + celda.reservas);
                    var pct = celda.disp > 0 ? Math.min(100, Math.round((valor / celda.disp) * 100)) : 0;
                    var bloqTxt = celda.bloq ? (" · " + celda.bloq + " bloq excluido" + (celda.bloq > 1 ? "s" : "")) : "";
                    el.className = "dashboard-hm-celda dashboard-hm-lvl-" + nivelVioleta(pct);
                    el.dataset.tooltip = dias[dIdx] + " " + horaTxt + " · " + pct + "% (" + valor + " de " + celda.disp + " turnos · " + celda.clases + " cl · " + celda.reservas + " res" + bloqTxt + ")";
                }
                el.setAttribute("aria-label", el.dataset.tooltip);
                celdasEl.appendChild(el);
            });

            filaEl.appendChild(diaEl);
            filaEl.appendChild(celdasEl);
            grid.appendChild(filaEl);
        });

        var ejeX = document.createElement("div");
        ejeX.className = "dashboard-hm-fila dashboard-hm-eje-x";
        ejeX.appendChild(document.createElement("span"));

        var etiquetasX = document.createElement("div");
        etiquetasX.className = "dashboard-hm-celdas";
        etiquetasX.style.gridTemplateColumns = "repeat(" + horas.length + ", minmax(0, 1fr))";
        horas.forEach(function (hora, idx) {
            var celdaX = document.createElement("div");
            celdaX.className = "dashboard-hm-x-celda";
            if (idx % 3 === 0 || idx === horas.length - 1) {
                var lbl = document.createElement("span");
                lbl.className = "dashboard-hm-x-etiqueta";
                lbl.textContent = String(hora).padStart(2, "0") + "h";
                celdaX.appendChild(lbl);
            }
            etiquetasX.appendChild(celdaX);
        });
        ejeX.appendChild(etiquetasX);
        grid.appendChild(ejeX);
    }

    if (selectorSede) {
        selectorSede.addEventListener("change", function () {
            sedeActual = selectorSede.value;
            renderHeatmap();
        });
    }
    document.querySelectorAll("[data-hm-tipo]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            tipoActual = btn.dataset.hmTipo;
            document.querySelectorAll("[data-hm-tipo]").forEach(function (otro) {
                otro.dataset.active = String(otro === btn);
            });
            renderHeatmap();
        });
    });

    renderHeatmap(true);
});
