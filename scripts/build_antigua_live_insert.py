#!/usr/bin/env python3
"""Build the INSERT for the antigua.live scrape: one es/en pair per series.

Reads data/antigua_live_events_2026-09-27_2026-10-04.json (107 occurrences) and
writes data/antigua_live_insert.sql. Series already in public.events (Cervecería
Catorce, Las Palmas x2, El Depósito, Aqua) are left out, and two listings that
are the same class twice (Socialtel, Las Vibras) are merged.

The SQL disables notify_town_on_event for the transaction, so the insert does not
send one push per row to everyone in Antigua.
"""
import json
import re
from pathlib import Path

SRC = Path("data/antigua_live_events_2026-09-27_2026-10-04.json")
OUT = Path("data/antigua_live_insert.sql")
TOWN_ID = 4

# Sun=0 .. Sat=6, same as the existing rows.
SUN, MON, TUE, WED, THU, FRI, SAT = range(7)
DAILY = [SUN, MON, TUE, WED, THU, FRI, SAT]

# (host, title) on antigua.live -> row content. `merge` lists other source
# series folded into this one (same class listed twice).
SERIES = [
    dict(key=("Angie Angie", "2x1 Pizza"), days=[SUN], start="12:00",
         name_es="Pizza 2x1 en Angie Angie", name_en="2-for-1 Pizza at Angie Angie",
         label_es="Domingos, 12:00-10:30pm", label_en="Sundays, 12:00-10:30pm",
         desc_es="Pizza 2x1 todos los domingos en el patio-jardín artístico de Angie Angie, con toque argentino, fogata y música en vivo.",
         desc_en="2-for-1 pizza every Sunday in Angie Angie's artsy garden courtyard, with an Argentinian flair, a fire pit and live music."),
    dict(key=("Caoba Farms", "Salsa in the Garden"), days=[SUN], start="11:00",
         name_es="Salsa en el jardín en Caoba Farms", name_en="Salsa in the Garden at Caoba Farms",
         label_es="Domingos, 11:00am-12:00pm", label_en="Sundays, 11:00am-12:00pm",
         cost_es="Q50 por persona", cost_en="Q50 per person",
         desc_es="Clase de salsa con José Medina rodeado de naturaleza en Caoba Farms. No necesitas experiencia: ven solo o con amigos.",
         desc_en="A salsa class with Jose Medina surrounded by nature at Caoba Farms. No experience needed; come solo or with friends."),
    dict(key=("Socialtel Hostel", "Discover the art of pizza making"), days=[SUN], start="16:00",
         name_es="Taller de pizza en Socialtel", name_en="Pizza-Making Workshop at Socialtel",
         label_es="Domingos, 4:00pm", label_en="Sundays, 4:00pm",
         cost_es="Q78 ($10) por persona", cost_en="Q78 ($10) per person",
         desc_es="Taller práctico para preparar y formar tu propia pizza desde cero, con música y buen ambiente. Ideal para ir solo o con amigos.",
         desc_en="A hands-on workshop where you prepare and shape your own pizza from scratch, with music and a relaxed crowd. Good solo or with friends."),
    dict(key=("Hot Chipilin", "Live Music and DJs"), days=DAILY, start="21:00",
         name_es="Música en vivo y DJs en Hot Chipilin", name_en="Live Music and DJs at Hot Chipilin",
         label_es="Diario, 9:00pm", label_en="Daily, 9:00pm",
         desc_es="Restaurante y bar con bandas en vivo todas las noches desde las 9pm, cocina guatemalteca e internacional y cócteles de autor. Revisa sus redes para el line-up.",
         desc_en="A funky restaurant and bar with live bands every night from 9pm, Guatemalan and international food, and signature cocktails. Check their socials for the line-up."),
    dict(key=("Café No Sé", "Live Music"), days=DAILY, start="21:30",
         name_es="Música en vivo en Café No Sé", name_en="Live Music at Café No Sé",
         label_es="Diario, 9:30pm", label_en="Daily, 9:30pm",
         desc_es="Música en vivo todas las noches en uno de los bares más conocidos de Antigua, desde las 9:30pm hasta que el cuerpo aguante.",
         desc_en="Live music every night at one of Antigua's best-known bars, from 9:30pm until whenever."),
    dict(key=("Caoba Farms", "Live Music"), days=[SUN, SAT], start="10:00",
         name_es="Música en vivo en Caoba Farms", name_en="Live Music at Caoba Farms",
         label_es="Sáb-dom, 10:00am-3:00pm", label_en="Sat-Sun, 10:00am-3:00pm",
         desc_es="Música en vivo los fines de semana en el restaurante de la granja Caoba, con comida hecha con ingredientes de su propia granja y pizzas de horno de leña.",
         desc_en="Weekend live music at Caoba's farm-to-table restaurant, with food made from ingredients grown on the farm and wood-fired pizzas."),
    dict(key=("The Snug", "Live Music"), days=[SUN, THU], start="19:00",
         name_es="Música en vivo en The Snug", name_en="Live Music at The Snug",
         label_es="Jue y dom, 7:00-9:00pm", label_en="Thu & Sun, 7:00-9:00pm",
         desc_es="Música en vivo en el único pub irlandés de Antigua, con terraza y vista a los volcanes. Punto de encuentro favorito de expatriados.",
         desc_en="Live music at Antigua's only Irish pub, with a terrace and volcano views. A favorite expat hangout."),
    dict(key=("Antigua Brewing Company", "Live Music and DJ"), days=[SUN, THU, FRI, SAT], start="17:00",
         name_es="Música en vivo y DJ en Antigua Brewing Company", name_en="Live Music and DJ at Antigua Brewing Company",
         label_es="Jue-dom, 5:00-11:00pm", label_en="Thu-Sun, 5:00-11:00pm",
         desc_es="Música en vivo y DJs de jueves a domingo en la cervecería Antigua Brewing. Revisa sus redes para el line-up de cada noche.",
         desc_en="Live music and DJs Thursday through Sunday at Antigua Brewing. Check their socials for each night's line-up."),
    dict(key=("El Patio de la Primera", "Live Music"), days=[SUN, WED, THU, FRI, SAT], start=None,
         name_es="Música en vivo en El Patio de la Primera", name_en="Live Music at El Patio de la Primera",
         label_es="Mié 7:30pm, jue-vie 7:00pm, sáb 12:00pm, dom 9:00am",
         label_en="Wed 7:30pm, Thu-Fri 7:00pm, Sat 12:00pm, Sun 9:00am",
         desc_es="Buena comida, música en vivo y ambiente cada semana en El Patio de la Primera, con presentaciones de miércoles a domingo.",
         desc_en="Good food, live music and atmosphere every week at El Patio de la Primera, with performances Wednesday through Sunday."),
    dict(key=("Hotel Soleil La Antigua", "Marimba Buffet Breakfast"), days=None, start="08:00", date="2026-09-27",
         name_es="Desayuno buffet con marimba en Hotel Soleil", name_en="Marimba Buffet Breakfast at Hotel Soleil",
         label_es="Dom 27 sep, 8:00-11:00am", label_en="Sun Sep 27, 8:00-11:00am",
         venue="Hotel Soleil La Antigua (Restaurante Las Chimeneas)",
         cost_es="Desde Q150 adultos, Q115 niños", cost_en="From Q150 adults, Q115 kids",
         phone="4739-2278 (WhatsApp) / 7774-4444",
         desc_es="Desayuno buffet con marimba en vivo en el Restaurante Las Chimeneas del Hotel Soleil. Es el último domingo de la temporada de agosto-septiembre. Reservaciones por WhatsApp; aplican restricciones.",
         desc_en="Buffet breakfast with live marimba at Hotel Soleil's Las Chimeneas restaurant. This is the last Sunday of the August-September run. Book by WhatsApp; restrictions apply."),
    dict(key=("Mayaflora S.A.", "Second Pumpkin Patch Festival"), days=None, start="09:30", date="2026-09-27",
         name_es="Segundo Festival de Calabazas en Mayaflora", name_en="Second Pumpkin Patch Festival at Mayaflora",
         label_es="Dom 27 sep y dom 4 oct, 9:30am-4:00pm", label_en="Sun Sep 27 & Sun Oct 4, 9:30am-4:00pm",
         venue="Mayaflora", cost_es="Q30 por persona (menores de 2 gratis)", cost_en="Q30 per person (under 2 free)",
         phone="5212-3048",
         desc_es="Un día familiar entre calabazas, colores de otoño y naturaleza en San Pedro Las Huertas. Hay taller de flores y calabazas a las 10am (Q200 con materiales, inscripción al 5212-3048) y pintura y tallado de calabazas de 10am a 4pm (precio de la calabaza + Q25). Q10 de descuento si llegas en bicicleta o en grupo de 10 o más.",
         desc_en="A family day among pumpkins, autumn colors and nature in San Pedro Las Huertas. There's a flowers-and-pumpkins workshop at 10am (Q200 with materials, sign up at 5212-3048) and pumpkin painting and carving from 10am to 4pm (price of the pumpkin + Q25). Q10 off if you arrive by bike or in a group of 10 or more."),
    dict(key=("Antigua Brewing Company", "Country Music Night"), days=[MON], start=None,
         name_es="Noche country en Antigua Brewing Company", name_en="Country Music Night at Antigua Brewing Company",
         label_es="Lunes", label_en="Mondays",
         desc_es="Botas, cerveza artesanal y los mejores éxitos country todos los lunes en Antigua Brewing Company. Ambiente relajado para bailar y conocer gente.",
         desc_en="Boots, craft beer and the best country hits every Monday at Antigua Brewing Company. A relaxed night to dance and meet people."),
    dict(key=("Hot Chipilin", "Open Mic"), days=[MON], start="20:00",
         name_es="Open mic y karaoke en Hot Chipilin", name_en="Open Mic & Karaoke at Hot Chipilin",
         label_es="Lunes, 8:00pm", label_en="Mondays, 8:00pm",
         desc_es="Los lunes son de karaoke en Hot Chipilin: canta tus canciones favoritas con tus amigos y llévate un shot gratis por participar.",
         desc_en="Mondays are karaoke night at Hot Chipilin: sing your favorite songs with friends and get a free shot for taking part."),
    dict(key=("The Snug", "Open Mic"), days=[MON], start="18:00",
         name_es="Open mic en The Snug", name_en="Open Mic at The Snug",
         label_es="Lunes, 6:00-9:00pm", label_en="Mondays, 6:00-9:00pm",
         desc_es="Open mic todos los lunes en el único pub irlandés de Antigua, con terraza y vista a los volcanes.",
         desc_en="Open mic every Monday at Antigua's only Irish pub, with a terrace and volcano views."),
    dict(key=("New Sensation Salsa Studio", "Free Salsa Classes"), days=[MON], start="17:00",
         name_es="Clases de salsa gratis en New Sensation", name_en="Free Salsa Classes at New Sensation",
         label_es="Lunes, 5:00-6:00pm", label_en="Mondays, 5:00-6:00pm",
         cost_es="Gratis", cost_en="Free",
         desc_es="Aprende salsa, haz amigos y practica tu español en las clases grupales gratuitas de New Sensation.",
         desc_en="Learn salsa, make friends and practice your Spanish at New Sensation's free group classes."),
    dict(key=("Casa Paraiso", "Productive Coworking"), days=[MON], start="09:00",
         name_es="Coworking productivo en Casa Paraíso", name_en="Productive Coworking at Casa Paraíso",
         label_es="Lunes, 9:00am-7:00pm", label_en="Mondays, 9:00am-7:00pm",
         venue="Casa Paraíso", cost_es="Entrada gratis (parqueo Q15/hora)", cost_en="Free entry (parking Q15/hour)",
         desc_es="Un espacio para enfocarte y sacar pendientes: WiFi rápido, espacios abiertos, música para concentrarte, casilleros para el teléfono y sin límite de tiempo.",
         desc_en="A space to focus and clear your to-do list: fast WiFi, open spaces, music to help you concentrate, phone lockers and no time limit."),
    dict(key=("Akai Sushi & Oriental", "2x1 Sushi"), days=[TUE, THU], start="12:00",
         name_es="Sushi 2x1 en Akai", name_en="2-for-1 Sushi at Akai",
         label_es="Mar y jue, 12:00-8:30pm", label_en="Tue & Thu, 12:00-8:30pm",
         venue="Akai Sushi & Oriental",
         desc_es="Sushi 2x1 todos los martes y jueves en Akai Sushi & Oriental.",
         desc_en="2-for-1 sushi every Tuesday and Thursday at Akai Sushi & Oriental."),
    dict(key=("Sunshine Grill and Pizzeria", "Game Day"), days=[TUE], start="16:00",
         name_es="Tarde de juegos en Sunshine Grill", name_en="Game Day at Sunshine Grill",
         label_es="Martes, 4:00-6:00pm", label_en="Tuesdays, 4:00-6:00pm",
         cost_es="Gratis", cost_en="Free",
         desc_es="Tarde de juegos de mesa todos los martes a las 4pm, organizada por Greg. Sin costo, solo diversión.",
         desc_en="Game day every Tuesday at 4pm, hosted by Greg. No charge, just fun."),
    dict(key=("Antigua Brewing Company", "Salsa Music Night"), days=[TUE], start="20:00",
         name_es="Noche de salsa en Antigua Brewing Company", name_en="Salsa Night at Antigua Brewing Company",
         label_es="Martes, 8:00-10:00pm", label_en="Tuesdays, 8:00-10:00pm",
         desc_es="Noche de música salsa todos los martes de 8 a 10pm en Antigua Brewing Company.",
         desc_en="Salsa music night every Tuesday from 8 to 10pm at Antigua Brewing Company."),
    dict(key=("The Snug", "Trivia Night"), days=[TUE], start="19:00",
         name_es="Noche de trivia en The Snug", name_en="Trivia Night at The Snug",
         label_es="Martes, 7:00pm", label_en="Tuesdays, 7:00pm",
         desc_es="Trivia todos los martes en el único pub irlandés de Antigua, con terraza y vista a los volcanes.",
         desc_en="Trivia every Tuesday at Antigua's only Irish pub, with a terrace and volcano views."),
    dict(key=("Reilly's", "Ladies Nights"), days=[TUE], start="20:00",
         name_es="Ladies Night en Reilly's", name_en="Ladies Night at Reilly's",
         label_es="Martes, 8:00pm", label_en="Tuesdays, 8:00pm",
         desc_es="Ladies Night todos los martes desde las 8pm en Reilly's, el legendario pub irlandés con billar y dardos que de noche se vuelve una de las mejores fiestas de Antigua.",
         desc_en="Ladies Night every Tuesday from 8pm at Reilly's, the legendary Irish pub with pool and darts that turns into one of Antigua's best parties at night."),
    dict(key=("Socialtel Hostel", "Salsa Lessons"), merge=[("Socialtel Hostel", "Free Salsa Classes")],
         days=[TUE], start="20:00",
         name_es="Clases de salsa en Socialtel", name_en="Salsa Lessons at Socialtel",
         label_es="Martes, 8:00-9:30pm", label_en="Tuesdays, 8:00-9:30pm",
         cost_es="Gratis", cost_en="Free",
         desc_es="Clase de salsa gratis con New Sensation en Socialtel Antigua, seguida de baile y bebidas 2x1. No necesitas experiencia; perfecta para conocer gente.",
         desc_en="A free salsa class with New Sensation at Socialtel Antigua, followed by dancing and 2-for-1 drinks. No experience needed; great for meeting people."),
    dict(key=("Kaldi & Kapra Coffee House", "Latte Art Workshop"), days=[TUE, THU], start="17:30",
         name_es="Taller de latte art en Kaldi & Kapra", name_en="Latte Art Workshop at Kaldi & Kapra",
         label_es="Mar y jue, 5:30pm", label_en="Tue & Thu, 5:30pm",
         cost_es="Q250 por persona", cost_en="Q250 per person", phone="3018-1844",
         desc_es="Aprende a texturizar leche y a verter latte art con guía personalizada. Practicas primero con jabón y luego preparas tres lattes. Reserva por DM o al 3018-1844.",
         desc_en="Learn milk texturing and latte-art pouring with one-on-one guidance. You practice with soap first, then make three lattes. Book by DM or at 3018-1844."),
    dict(key=("Suaf Bar", "Introducing the Anti-Algorithm Club."), days=[WED], start="17:00",
         name_es="Anti-Algorithm Club en Suaf Bar", name_en="Anti-Algorithm Club at Suaf Bar",
         label_es="Miércoles, 5:00-11:00pm", label_en="Wednesdays, 5:00-11:00pm",
         desc_es="Una reunión semanal para descubrir música a la antigua: trae un disco que te tenga obsesionado y lo ponen. Tu primer trago de la casa va por cuenta de ellos.",
         desc_en="A weekly gathering for discovering music the old-school way: bring a record you're obsessed with and they'll put it on. Your first house drink is on them."),
    dict(key=("Las Vibras", "LADIES NIGHT"), days=[WED], start="21:00",
         name_es="Ladies Night en Las Vibras", name_en="Ladies Night at Las Vibras",
         label_es="Miércoles, 9:00pm", label_en="Wednesdays, 9:00pm",
         cost_es="Entrada gratis", cost_en="Free entry",
         desc_es="Todos los miércoles la pista se enciende en Las Vibras: tragos gratis para mujeres desde las 9pm y entrada libre.",
         desc_en="Every Wednesday the dance floor comes alive at Las Vibras: free drinks for ladies from 9pm and free entry."),
    dict(key=("The Londoner", "Midweek just got better"), days=[WED], start="18:00",
         name_es="Pub quiz en The Londoner", name_en="Pub Quiz at The Londoner",
         label_es="Miércoles, 6:00pm", label_en="Wednesdays, 6:00pm",
         cost_es="Q10 por persona", cost_en="Q10 per person",
         desc_es="Pub quiz todos los miércoles en The Londoner: arma tu equipo, pon a prueba lo que sabes y disfruta la mitad de semana por Q10.",
         desc_en="Pub quiz every Wednesday at The Londoner: bring your crew, test your knowledge and enjoy midweek for Q10."),
    dict(key=("Antigua Brewing Company", "Open Mic"), days=[WED], start="20:00",
         name_es="Open mic en Antigua Brewing Company", name_en="Open Mic at Antigua Brewing Company",
         label_es="Miércoles, 8:00-10:00pm", label_en="Wednesdays, 8:00-10:00pm",
         desc_es="Open mic todos los miércoles a las 8pm en Antigua Brewing Company.",
         desc_en="Open mic every Wednesday at 8pm at Antigua Brewing Company."),
    dict(key=("Hot Chipilin", "Free Salsa Classes"), days=[WED], start="17:00",
         name_es="Clases de salsa gratis en Hot Chipilin", name_en="Free Salsa Classes at Hot Chipilin",
         label_es="Miércoles, 5:00-6:00pm", label_en="Wednesdays, 5:00-6:00pm",
         cost_es="Gratis", cost_en="Free",
         desc_es="Aprende salsa, haz amigos y practica tu español en las clases grupales gratuitas de New Sensation en Hot Chipilin.",
         desc_en="Learn salsa, make friends and practice your Spanish at New Sensation's free group classes at Hot Chipilin."),
    dict(key=("Casa Paraiso", "Tango Social Club"), days=[WED], start="19:30",
         name_es="Tango Social Club en Casa Paraíso", name_en="Tango Social Club at Casa Paraíso",
         label_es="Miércoles, 7:30-8:30pm", label_en="Wednesdays, 7:30-8:30pm",
         venue="Casa Paraíso", cost_es="Q80 por clase, Q280 por 4 clases", cost_en="Q80 per class, Q280 for 4 classes",
         phone="3134-7107",
         desc_es="Clases de tango para bailar con elegancia, técnica y conexión, tanto para principiantes como para quienes quieren pulir sus pasos.",
         desc_en="Tango classes to help you dance with elegance, technique and connection, for beginners and for anyone refining their moves."),
    dict(key=("Socialtel Hostel", "Antigua Bar Crawl"), days=[WED], start="20:00",
         name_es="Bar crawl de Socialtel", name_en="Socialtel Bar Crawl",
         label_es="Miércoles, 8:00pm-1:00am", label_en="Wednesdays, 8:00pm-1:00am",
         cost_es="Gratis", cost_en="Free",
         desc_es="Recorrido guiado por algunos de los mejores bares de Antigua con shots de cortesía en el camino. Punto de encuentro: Socialtel Antigua.",
         desc_en="A guided tour of some of Antigua's best bars, with complimentary shots along the way. Meeting point: Socialtel Antigua."),
    dict(key=("Soul Dance Project", "Shotokan Karate-Do Classes"), days=[WED, SAT], start=None,
         name_es="Clases de karate Shotokan en Soul Dance Project", name_en="Shotokan Karate Classes at Soul Dance Project",
         label_es="Mié 4:00pm, sáb 10:00am", label_en="Wed 4:00pm, Sat 10:00am",
         phone="3652-1593 (WhatsApp)",
         desc_es="Karate-Do Shotokan tradicional para todas las edades, en inglés y español, sin experiencia previa. Frente al parque de San Gaspar Vivar. Inscripción por WhatsApp.",
         desc_en="Traditional Shotokan Karate-Do for all ages, taught in English and Spanish, no experience required. Across from San Gaspar Vivar park. Register by WhatsApp."),
    dict(key=("Bullseye Sports Pub", "Karaoke"), days=[WED], start="20:00",
         name_es="Karaoke en Bullseye", name_en="Karaoke at Bullseye",
         label_es="Miércoles, 8:00pm", label_en="Wednesdays, 8:00pm",
         desc_es="Karaoke en Bullseye Sports Pub, bar deportivo pet-friendly con cerveza artesanal de barril, a pasos del parque central en el complejo El Barrio.",
         desc_en="Karaoke at Bullseye Sports Pub, a pet-friendly sports bar with craft beer on tap, steps from the main square in the El Barrio complex."),
    dict(key=("Charleston Antigua", "CLANDESTINE NIGHTS"), days=[WED, THU], start="16:00",
         name_es="Clandestine Nights en Charleston", name_en="Clandestine Nights at Charleston",
         label_es="Mié y jue, 4:00pm", label_en="Wed & Thu, 4:00pm",
         desc_es="Pasa detrás del espejo en Charleston para una noche de destilados: gin Macera los miércoles y mezcal Sagrada los jueves. Consulta horarios con el lugar.",
         desc_en="Step behind the mirror at Charleston for a spirits night: Macera gin on Wednesdays and Mezcal Sagrada on Thursdays. Check times with the venue."),
    dict(key=("Bullseye Sports Pub", "Trivia Night"), days=[THU], start="20:00",
         name_es="Noche de trivia en Bullseye", name_en="Trivia Night at Bullseye",
         label_es="Jueves, 8:00pm", label_en="Thursdays, 8:00pm",
         desc_es="Trivia todos los jueves a las 8pm en Bullseye Sports Pub, bar deportivo pet-friendly a pasos del parque central.",
         desc_en="Trivia every Thursday at 8pm at Bullseye Sports Pub, a pet-friendly sports bar steps from the main square."),
    dict(key=("Las Vibras", "Jueves Latino"), merge=[("Las Vibras", "Free Salsa Classes")],
         days=[THU], start="20:00",
         name_es="Jueves Latino en Las Vibras", name_en="Latin Thursdays at Las Vibras",
         label_es="Jueves, 8:00pm", label_en="Thursdays, 8:00pm",
         cost_es="Entrada gratis", cost_en="Free entry",
         desc_es="Noche latina con clase de baile gratis de 8 a 9pm, DJ en vivo, promociones toda la noche y pizza 2x1 en la terraza.",
         desc_en="A Latin night with a free dance class from 8 to 9pm, a live DJ, specials all night and 2-for-1 pizza on the terrace."),
    dict(key=("Whisky Den & Coffee Bar", "Miami Lounge Nights are back."), days=[THU], start="20:30",
         name_es="Miami Lounge Nights en Whisky Den", name_en="Miami Lounge Nights at Whisky Den",
         label_es="Jueves, 8:30pm", label_en="Thursdays, 8:30pm",
         venue="Whisky Den & Coffee Bar", phone="3532-7972",
         desc_es="DJ Piloy, residente de Whisky Den, pone ritmos tropicales toda la noche mientras preparan cócteles de autor inspirados en la vida nocturna de Miami.",
         desc_en="Whisky Den resident DJ Piloy spins tropical beats all night while the bartenders mix signature cocktails inspired by Miami nightlife."),
    dict(key=("Restaurante La Santa", "Theater Club for Kids"), days=[FRI], start="10:00",
         name_es="Club de teatro para niños en La Santa", name_en="Kids' Theater Club at La Santa",
         label_es="Viernes, 10:00-11:30am y 3:00-4:30pm", label_en="Fridays, 10:00-11:30am & 3:00-4:30pm",
         phone="4247-0110",
         desc_es="Laboratorio de actuación para niños de 7 años en adelante: juegos, expresión y confianza a través de la imaginación. Reserva tu lugar al 4247-0110.",
         desc_en="An acting lab for kids 7 and up: games, self-expression and confidence through imagination. Reserve a spot at 4247-0110."),
    dict(key=("Salsa Y Más", "Latin Dance Group Classes"), days=[FRI, SAT], start="18:00",
         name_es="Clases grupales de baile latino en Salsa y Más", name_en="Latin Dance Group Classes at Salsa y Más",
         label_es="Vie-sáb, 6:00, 7:00 y 8:00pm", label_en="Fri-Sat, 6:00, 7:00 & 8:00pm",
         venue="Salsa y Más", cost_es="Q350 al mes", cost_en="Q350 per month",
         phone="5525-7763 / 4078-9147",
         desc_es="Merengue, bachata, cumbia, salsa y más en clases grupales con instructores profesionales, para principiantes o quienes quieren mejorar. Pregunta por promociones.",
         desc_en="Merengue, bachata, cumbia, salsa and more in group classes led by professional instructors, for beginners or anyone improving. Ask about current promotions."),
    dict(key=("Fuego Yoga", "TAI CHI CLASS"), days=[SAT], start="10:00",
         name_es="Tai chi en Fuego Yoga", name_en="Tai Chi at Fuego Yoga",
         label_es="Sábados, 10:00am", label_en="Saturdays, 10:00am",
         cost_es="Q90 por clase", cost_en="Q90 per class",
         desc_es="Sesión de tai chi los sábados para bajar el ritmo, reconectar y encontrar equilibrio. Reserva tu lugar.",
         desc_en="A Saturday tai chi session to slow down, reconnect and find balance. Reserve your spot."),
    dict(key=("Mamma Yamma Cooking Class", "Tamalada Ritual"), days=[SAT], start="16:30",
         name_es="Tamalada con David Farfán", name_en="Tamale Day with David Farfan",
         label_es="Sábados, 4:30-7:00pm", label_en="Saturdays, 4:30-7:00pm",
         cost_es="$50 por persona", cost_en="$50 per person",
         desc_es="Aprende a preparar distintos tamales en grupo con David Farfán. Incluye tu propia tanda de tamales, postre de mole de chocolate y bebidas.",
         desc_en="Learn to make several kinds of tamales in a group with David Farfan. Includes your own batch of tamales, a chocolate mole dessert and drinks."),
    dict(key=("Fuego Yoga", "THE WEEKEND BURN"), days=[SAT], start="10:00",
         name_es="The Weekend Burn en Fuego Yoga", name_en="The Weekend Burn at Fuego Yoga",
         label_es="Sábados, 10:00am-5:00pm", label_en="Saturdays, 10:00am-5:00pm",
         desc_es="Sábado de comunidad en Fuego Yoga: tai chi a las 10am y de 12 a 5pm mercado artesanal, lectura de tarot, flash tattoos y barbacoa.",
         desc_en="A community Saturday at Fuego Yoga: tai chi at 10am, then from 12 to 5pm an artisan market, tarot readings, flash tattoos and BBQ."),
    dict(key=("Aruma Bistro Art Gallery", "From clay to resin… from idea to reality. 🎨"), days=[SAT], start="10:30",
         name_es="Taller de arcilla y resina en Aruma", name_en="Clay and Resin Workshop at Aruma",
         label_es="Sábados, 10:30am", label_en="Saturdays, 10:30am",
         venue="Aruma Art Gallery", cost_es="$315 (curso completo)", cost_en="$315 (full course)",
         desc_es="Modela, texturiza y convierte tu idea en una pieza final de resina. Cupo limitado; escríbeles por DM para apartar tu lugar.",
         desc_en="Shape, texture and turn your idea into a finished resin piece. Spots are limited; DM them to save yours."),
]

# Already in public.events (rows 317-328 and legacy rows) -> skipped.
DUPLICATES_IN_DB = {
    ("Cervecería Catorce", "Live Music"): "321/322",
    ("Las Palmas", "Live Music"): "325/326",
    ("Las Palmas", "Free Salsa Classes"): "317/318",
    ("El Depósito", "Live Music"): "319/320",
    ("Aqua Antigua", "Saturday Nights Are Better"): "327/328",
}


def q(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def contact_link(links):
    links = [l.replace("%20", "").rstrip() for l in links if "vidaantigua.com" not in l]
    for host in ("facebook.com", "instagram.com"):
        for l in links:
            if host in l:
                return l
    return links[0] if links else None


def phone(raw):
    # +50252123048 -> 5212-3048
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("502") and len(digits) == 11:
        digits = digits[3:]
    return f"{digits[:4]}-{digits[4:]}" if len(digits) == 8 else None


def main():
    events = json.loads(SRC.read_text())["events"]
    by_key = {}
    for e in events:
        by_key.setdefault((e["host"], e["title"]), []).append(e)

    covered = set(DUPLICATES_IN_DB)
    rows = []
    for s in SERIES:
        occ = by_key[s["key"]]
        for m in s.get("merge", []):
            covered.add(m)
        covered.add(s["key"])
        first = min(occ, key=lambda e: e["date"])
        common = dict(
            town_id=TOWN_ID,
            cover_image=first["image"],
            calendar_date=s.get("date", first["date"]),
            start_time=s["start"],
            venue=s.get("venue", s["key"][0]),
            contact_number=s.get("phone") or phone(first["phone"]),
            contact_link=contact_link(first["links"]),
            recurring_days=s["days"],
        )
        for lang in ("es", "en"):
            rows.append(dict(common, lang=lang, name=s[f"name_{lang}"], description=s[f"desc_{lang}"],
                             event_date_label=s[f"label_{lang}"], cost=s.get(f"cost_{lang}")))

    missing = set(by_key) - covered
    assert not missing, f"series not handled: {missing}"

    cols = ["town_id", "name", "description", "cover_image", "event_date_label", "calendar_date",
            "start_time", "venue", "cost", "contact_number", "contact_link", "is_approved",
            "is_feature", "lang", "recurring_days"]
    values = []
    for r in rows:
        days = "null" if r["recurring_days"] is None else \
            "array[" + ",".join(map(str, r["recurring_days"])) + "]::smallint[]"
        values.append("(" + ", ".join([
            str(r["town_id"]), q(r["name"]), q(r["description"]), q(r["cover_image"]),
            q(r["event_date_label"]), q(r["calendar_date"]) + "::date",
            (q(r["start_time"]) + "::time") if r["start_time"] else "null",
            q(r["venue"]), q(r["cost"]), q(r["contact_number"]), q(r["contact_link"]),
            "true", "false", q(r["lang"]), days,
        ]) + ")")

    sql = (
        f"-- antigua.live, 2026-09-27..2026-10-04: {len(SERIES)} series, {len(rows)} rows (es/en).\n"
        "-- Generated by scripts/build_antigua_live_insert.py.\n"
        "-- notify_town_on_event is off for this transaction only: with it on, every\n"
        "-- approved row pushes to everyone in Antigua (one push per row).\n"
        "begin;\n"
        "alter table public.events disable trigger notify_town_on_event;\n\n"
        f"insert into public.events ({', '.join(cols)}) values\n"
        + ",\n".join(values)
        + "\nreturning id, lang, name;\n\n"
        "alter table public.events enable trigger notify_town_on_event;\n"
        "commit;\n"
    )
    OUT.write_text(sql)
    print(f"{len(SERIES)} series -> {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
