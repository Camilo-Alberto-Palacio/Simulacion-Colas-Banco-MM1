# GUION DE SUSTENTACIÓN — ACTIVIDAD DIDÁCTICA 2-M3
## Solución de un Problema Bancario con Modelos de Colas Independientes M/M/1 (Banco de Colombia)

* **Institución:** Institución Universitaria Digital de Antioquia (IU Digital) — Facultad de Ingeniería
* **Asignatura:** Simulación (`PREICA2602B020045`) — Grupo 25
* **Docente Catedrático:** Dr. Julián Andrés Loaiza López
* **Modalidad:** 1 Solo Presentador / Portavoz (en representación del Grupo 25)
* **Integrantes del Equipo:** Adriana Andrea Agudelo Agudelo, Camilo Alberto Palacios Turriago, Juan Daniel Pulgarin García y Ruben Dario Jaramillo Cervantes
* **Duración Objetivo:** **2 minutos y 30 segundos (Máximo permitido: 3:00 minutos)**
* **Formato:** Video horizontal (16:9), 1080p, pantalla compartida con las figuras de `results/` o el cuaderno Google Colab + cámara web en esquina

---

### ESTRUCTURA DEL PITCH (2:30 MINUTOS)

```text
[0:00 - 0:15]  1. Gancho: El dilema operativo del Banco de Colombia (70% retiros vs 30% pagos)
[0:15 - 0:40]  2. Contexto y Equipo: Presentación Grupo 25 y parametrización del sistema (8 horas)
[0:40 - 1:10]  3. Modelo M/M/1 y Escenarios: Teoría de colas independientes y 5 configuraciones
[1:10 - 1:55]  4. Resultados Clave: Puntos 1–3 (10 réplicas) y Puntos 4–5 (100 réplicas Monte Carlo)
[1:55 - 2:20]  5. Decisión Ejecutiva: ¿Crear un 4.º cajero? ¿Cuántos exclusivos de pagos y retiros?
[2:20 - 2:30]  6. Cierre: Repositorio GitHub, Google Colab y despedida
```

---

## 🎬 GUION COMPLETO PASO A PASO

> **[0:00 – 0:15] FASE 1: EL GANCHO (15 segundos)**  
> *(En pantalla: `results/fig1_arquitectura_colas_mm1.png`)*  
>  
> *"A simple vista, si el 70% de los usuarios de un banco viene a retirar dinero y solo el 30% a pagar o consignar, cualquiera pensaría que basta con asignar dos cajas para retiros y una sola para pagos. Pero cuando simulamos el tiempo real de atención, descubrimos que esa intuición genera un cuello de botella de casi 10 minutos de espera."*

---

> **[0:15 – 0:40] FASE 2: CONTEXTO Y EQUIPO (25 segundos)**  
> *(En pantalla: Tabla de parámetros y código en `bank_queue/model.py`)*  
>  
> *"Cordial saludo, profesor Julián Loaiza. A nombre del **Grupo 25** —integrado por Adriana Agudelo, Juan Daniel Pulgarin, Ruben Jaramillo y quien les habla, Camilo Palacios— presentamos la solución al caso del **Banco de Colombia**. Modelamos la sucursal de **3 cajas** durante jornadas de **8 horas (480 minutos)**, diferenciando los tiempos exponenciales de llegada y servicio para cuatro perfiles de usuario: Rápido, Normal, Lento y Muy lento."*

---

> **[0:40 – 1:10] FASE 3: MODELADO M/M/1 Y ESCENARIOS (30 segundos)**  
> *(En pantalla: `results/fig2_tiempos_atencion_por_cajero.png` y `results/fig3_distribucion_usuarios_por_tipo_replicas.png`)*  
>  
> *"Cada cajero se simuló como una cola **M/M/1 independiente** bajo disciplina FCFS, verificando primero analíticamente la estabilidad ($\rho < 1$) y la Ley de Little. En nuestras **10 réplicas oficiales** del escenario base de 3 cajas mixtas, identificamos que el **Cajero 2** registró el menor tiempo medio de servicio (**2.88 min**, sistema **6.22 min**) y el **Cajero 1** el mayor (**3.23 min**, sistema **7.49 min**). Asimismo, cuantificamos el promedio diario de **208.3 usuarios** y sus mínimos por réplica, donde la Réplica 5 concentró la menor afluencia en perfiles Rápido (30), Normal (62) y Muy lento (44)."*

---

> **[1:10 – 1:55] FASE 4: COMPARATIVA DE ESCENARIOS Y MONTE CARLO (45 segundos)**  
> *(En pantalla: `results/fig4_comparativa_espera_escenarios.png` y `results/fig6_balance_carga_cajeros_escenarios.png`)*  
>  
> *"Con base en las 10 réplicas piloto calculamos un tamaño muestral de 50 a 68 réplicas para acotar la espera a ±0.5 minutos al 95% t de Student, por lo que validamos todos los criterios en **100 réplicas Monte Carlo**. Los datos explican la paradoja inicial: aunque los retiros son el 70% del flujo, su servicio dura solo **2.34 minutos**, mientras que un pago tarda **5.20 minutos** en promedio. Por eso, en **2 Retiros + 1 Pago**, el único cajero de pagos se convierte en un cuello de botella con **9.08 minutos** de espera promedio (9.16 min en el peor promedio diario); y en **1 Retiro + 2 Pagos**, el cajero de retiros sube al **67.4% de ocupación**, espera **5.91 minutos** y eleva el promedio global a **4.94 minutos**."*

---

> **[1:55 – 2:20] FASE 5: DECISIÓN EJECUTIVA PARA BANCO DE COLOMBIA (25 segundos)**  
> *(En pantalla: `results/fig5_validacion_montecarlo_y_teoria.png`)*  
>  
> *"¿Qué recomendamos al Banco de Colombia? Primero, **mantener las 3 cajas en modalidad mixta** (0 exclusivas de retiro y 0 de pago), porque aprovechan la consolidación de colas: logran una espera promedio equilibrada de **3.24 minutos** (3.29 en retiros y 3.15 en pagos) —y apenas **0.74 minutos** con selección observable de cola más corta JSQ— manteniendo **43.7%** de ocupación. Segundo, **no es necesario crear un cuarto cajero físico ni electrónico**: aunque baja la espera a ~1.8–2.0 minutos, desploma la utilización al **32.9%**, dejando a los cajeros desocupados el **67.1% del día**."*

---

> **[2:20 – 2:30] FASE 6: CIERRE Y REPRODUCIBILIDAD (10 segundos)**  
> *(En pantalla: Repositorio en GitHub y Google Colab abierto)*  
>  
> *"El informe completo, la suite de 11 pruebas unitarias en Python, el cuaderno interactivo en Google Colab y todas las gráficas reproducibles quedan disponibles en nuestro repositorio de GitHub. ¡Muchas gracias!"*
