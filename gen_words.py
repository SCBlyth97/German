#!/usr/bin/env python3
"""
Generate words.json for the Deutsch flashcard app.

Strategy:
  1. Start with a curated list of ~540 high-frequency German nouns/verbs
     (enough buffer to hit 500 after any skips).
  2. Fetch wikitext from de.wiktionary.org in batches of 50 (MediaWiki API).
  3. Parse the wikitext with regex to extract:
       nouns  → genus (der/die/das) + plural
       verbs  → 3rd-sg-present, Präteritum, Perfekt + auxiliary
  4. Assign to groups 1..25 (20 words per group, frequency order).
  5. Write words.json.  Print a skip report at the end.
"""

import json, re, time, urllib.request, urllib.parse, sys

# ---------------------------------------------------------------------------
# WORD LIST  (frequency order, roughly; nouns capitalised, verbs lowercase)
# ~270 verbs + ~270 nouns = 540 candidates → target 250 of each after validation
# ---------------------------------------------------------------------------
VERBS = [
    "sein","haben","werden","können","müssen","sagen","machen","gehen","kommen",
    "wissen","sehen","lassen","stehen","finden","bleiben","liegen","heißen",
    "denken","nehmen","tun","glauben","halten","nennen","zeigen","führen",
    "arbeiten","spielen","sprechen","bringen","leben","fahren","fallen","folgen",
    "geben","handeln","helfen","hören","kaufen","kennen","laufen","lesen",
    "meinen","öffnen","schreiben","setzen","suchen","treffen","warten",
    "essen","trinken","schlafen","wohnen","lernen","verstehen","fragen",
    "antworten","beginnen","brauchen","vergessen","erinnern","sterben",
    "wachsen","kochen","waschen","fliegen","schwimmen","tanzen","singen",
    "gewinnen","verlieren","erklären","besuchen","bezahlen","danken",
    "entscheiden","entwickeln","erhalten","erreichen","erzählen","feiern",
    "fühlen","gefallen","gehören","hoffen","kämpfen","kosten","lachen",
    "lieben","mögen","passieren","planen","reden","reisen","schicken",
    "schmecken","teilen","tragen","versuchen","wählen","wünschen",
    "aufmachen","zumachen","einladen","aussteigen","einsteigen","umsteigen",
    "ankommen","abfahren","aufstehen","einschlafen","aufwachen","anrufen",
    "ausgehen","einkaufen","vorstellen","entschuldigen","bedeuten","gehören",
    "klingen","scheinen","erscheinen","verlassen","treiben","ziehen",
    "legen","stellen","hängen","werfen","schneiden","malen","bauen",
    "mieten","verkaufen","öffnen","schließen","drücken","ziehen","stoßen",
    "berühren","greifen","packen","heben","tragen","bringen","holen",
    "schicken","liefern","empfangen","bezahlen","wechseln","tauschen",
    "sparen","verdienen","vorbereiten","bestellen","reservieren","empfehlen",
    "erlauben","verbieten","gelingen","scheitern","verbessern","wiederholen",
    "aufhören","anfangen","benutzen","verwenden","ersetzen","hinzufügen",
    "entfernen","prüfen","testen","messen","zählen","berechnen","vergleichen",
    "beschreiben","überprüfen","analysieren","organisieren","kommunizieren",
    "diskutieren","zustimmen","ablehnen","akzeptieren","aufnehmen","aufzeichnen",
    "veröffentlichen","drucken","speichern","laden","installieren",
]

NOUNS = [
    "Mann","Frau","Kind","Jahr","Zeit","Hand","Stadt","Land","Welt","Tag",
    "Haus","Mensch","Arbeit","Leben","Wasser","Weg","Schule","Auto","Geld",
    "Essen","Buch","Tisch","Stuhl","Tür","Fenster","Bett","Boden","Wand",
    "Familie","Mutter","Vater","Bruder","Schwester","Sohn","Tochter",
    "Freund","Freundin","Lehrer","Schüler","Arzt","Polizist",
    "Firma","Büro","Bahnhof","Flughafen","Hotel","Restaurant",
    "Geschäft","Markt","Straße","Platz","Park","Berg","Fluss","See","Meer",
    "Hund","Katze","Vogel","Fisch","Pferd","Kuh","Schwein","Huhn",
    "Brot","Milch","Fleisch","Gemüse","Obst","Apfel","Kartoffel","Ei",
    "Kaffee","Tee","Bier","Wein","Teller","Glas","Flasche","Messer",
    "Gabel","Löffel","Jacke","Hose","Hemd","Kleid","Uhr","Telefon",
    "Computer","Schlüssel","Brief","Zeitung","Film","Musik","Kunst","Sport",
    "Spiel","Ball","Farbe","Licht","Stimme","Frage","Antwort","Problem",
    "Lösung","Idee","Meinung","Nachricht","Geschichte","Nummer","Name",
    "Wort","Satz","Sprache","Bild","Foto","Karte","Zimmer","Küche",
    "Bad","Garten","Dorf","Insel","Nacht","Morgen","Abend","Woche",
    "Monat","Stunde","Minute","Sekunde","Körper","Kopf","Auge","Ohr",
    "Nase","Mund","Zahn","Haar","Arm","Bein","Herz","Blut","Luft",
    "Erde","Feuer","Energie","Macht","Kraft","Freiheit","Wahrheit",
    "Liebe","Freude","Angst","Hoffnung","Traum","Gedanke","Gefühl",
    "Unterschied","Beispiel","Ergebnis","Möglichkeit","Aufgabe","Ziel",
    "Erfolg","Fehler","Chance","Risiko","Preis","Qualität","Menge",
    "Linie","Punkt","Form","Richtung","Entfernung","Gewicht","Größe",
    "Farbe","Gruppe","Teil","Stück","Reihe","Liste","Titel","Inhalt",
    "System","Netz","Programm","Datei","Seite","Text","Artikel",
    "Vertrag","Gesetz","Recht","Pflicht","Regel","Methode","Plan",
    "Projekt","Produkt","Marke","Modell","Typ","Art","Weise","Stil",
    "Schritt","Phase","Stufe","Ebene","Bereich","Thema","Begriff",
    "Wohnung","Straße","Brücke","Kirche","Krankenhaus","Apotheke","Bibliothek",
    "Museum","Kino","Theater","Konzert","Veranstaltung","Feier","Urlaub","Reise",
    "Gepäck","Koffer","Pass","Visum","Ticket","Fahrkarte","Fahrt","Strecke",
    "Entscheidung","Wahl","Möglichkeit","Gelegenheit","Einladung","Besuch",
    "Gespräch","Interview","Bericht","Aufsatz","Kommentar","Antwort",
    "Anfrage","Angebot","Bestellung","Rechnung","Quittung","Vertrag",
    "Versicherung","Steuer","Konto","Kredit","Schuld","Gehalt","Lohn",
    "Beruf","Stelle","Bewerbung","Ausbildung","Studium","Prüfung","Note",
    "Unterricht","Übung","Lösung","Aufgabe","Hausaufgabe","Lektion",
    "Kapitel","Abschnitt","Absatz","Seite","Zeile","Zeichen","Symbol",
    "Farbe","Muster","Design","Layout","Format","Größe","Maßstab",
    "Gewinn","Verlust","Umsatz","Kosten","Ausgabe","Einnahme","Ersparnis",
    "Werkzeug","Maschine","Gerät","Apparat","Instrument","Material",
    "Stoff","Holz","Metall","Plastik","Glas","Stein","Sand","Erde",
]

# ---------------------------------------------------------------------------
# Simple example sentences (we generate these ourselves; they're A1-A2 level)
# Keyed by the word ID (slug). Fallback sentence built programmatically below.
# ---------------------------------------------------------------------------
EXAMPLES = {
    # verbs
    "sein":       ("Ich bin müde.", "I am tired."),
    "haben":      ("Sie hat ein Buch.", "She has a book."),
    "werden":     ("Er wird Arzt.", "He is becoming a doctor."),
    "koennen":    ("Ich kann schwimmen.", "I can swim."),
    "muessen":    ("Du musst schlafen.", "You must sleep."),
    "sagen":      ("Er sagt die Wahrheit.", "He tells the truth."),
    "machen":     ("Wir machen Hausaufgaben.", "We do homework."),
    "gehen":      ("Ich gehe nach Hause.", "I'm going home."),
    "kommen":     ("Sie kommt aus Berlin.", "She comes from Berlin."),
    "wissen":     ("Ich weiß die Antwort.", "I know the answer."),
    "sehen":      ("Siehst du den Hund?", "Do you see the dog?"),
    "lassen":     ("Er lässt mich schlafen.", "He lets me sleep."),
    "stehen":     ("Das Buch steht im Regal.", "The book is on the shelf."),
    "finden":     ("Ich finde meinen Schlüssel nicht.", "I can't find my key."),
    "bleiben":    ("Wir bleiben zu Hause.", "We're staying home."),
    "liegen":     ("Die Katze liegt auf dem Sofa.", "The cat is lying on the sofa."),
    "heissen":    ("Wie heißt du?", "What is your name?"),
    "denken":     ("Ich denke an dich.", "I'm thinking of you."),
    "nehmen":     ("Nimmst du Zucker?", "Do you take sugar?"),
    "tun":        ("Was tust du gerade?", "What are you doing right now?"),
    "glauben":    ("Ich glaube dir.", "I believe you."),
    "halten":     ("Der Bus hält hier.", "The bus stops here."),
    "nennen":     ("Wir nennen ihn Max.", "We call him Max."),
    "zeigen":     ("Sie zeigt mir den Weg.", "She shows me the way."),
    "fuehren":    ("Der Weg führt zum Park.", "The path leads to the park."),
    "arbeiten":   ("Er arbeitet im Büro.", "He works in the office."),
    "spielen":    ("Die Kinder spielen im Park.", "The children play in the park."),
    "sprechen":   ("Sprechen Sie Deutsch?", "Do you speak German?"),
    "bringen":    ("Ich bringe das Buch.", "I'll bring the book."),
    "leben":      ("Sie lebt in Wien.", "She lives in Vienna."),
    "fahren":     ("Wir fahren mit dem Zug.", "We travel by train."),
    "fallen":     ("Das Blatt fällt vom Baum.", "The leaf falls from the tree."),
    "folgen":     ("Folg mir bitte!", "Please follow me!"),
    "geben":      ("Kannst du mir einen Stift geben?", "Can you give me a pen?"),
    "handeln":    ("Es handelt sich um ein Problem.", "It's about a problem."),
    "helfen":     ("Kann ich dir helfen?", "Can I help you?"),
    "hoeren":     ("Ich höre Musik.", "I'm listening to music."),
    "kaufen":     ("Er kauft Brot im Supermarkt.", "He buys bread at the supermarket."),
    "kennen":     ("Kennst du Berlin?", "Do you know Berlin?"),
    "laufen":     ("Sie läuft jeden Morgen.", "She runs every morning."),
    "lesen":      ("Ich lese ein Buch.", "I'm reading a book."),
    "meinen":     ("Was meinst du?", "What do you think?"),
    "oeffnen":    ("Er öffnet die Tür.", "He opens the door."),
    "schreiben":  ("Sie schreibt einen Brief.", "She writes a letter."),
    "setzen":     ("Er setzt sich auf den Stuhl.", "He sits down on the chair."),
    "suchen":     ("Ich suche meine Jacke.", "I'm looking for my jacket."),
    "treffen":    ("Wir treffen uns um drei.", "We meet at three."),
    "warten":     ("Sie wartet auf den Bus.", "She's waiting for the bus."),
    "essen":      ("Ich esse gerne Pizza.", "I like eating pizza."),
    "trinken":    ("Er trinkt Kaffee.", "He drinks coffee."),
    "schlafen":   ("Das Kind schläft schon.", "The child is already asleep."),
    "wohnen":     ("Wo wohnst du?", "Where do you live?"),
    "lernen":     ("Ich lerne Deutsch.", "I'm learning German."),
    "verstehen":  ("Ich verstehe nicht.", "I don't understand."),
    "fragen":     ("Darf ich fragen?", "May I ask?"),
    "antworten":  ("Er antwortet auf die Frage.", "He answers the question."),
    "beginnen":   ("Der Unterricht beginnt um acht.", "Class begins at eight."),
    "brauchen":   ("Ich brauche Hilfe.", "I need help."),
    "vergessen":  ("Ich vergesse immer meinen Schlüssel.", "I always forget my key."),
    "erinnern":   ("Ich erinnere mich an ihn.", "I remember him."),
    "sterben":    ("Die Blume stirbt ohne Wasser.", "The flower dies without water."),
    "wachsen":    ("Die Kinder wachsen schnell.", "The children grow quickly."),
    "kochen":     ("Meine Mutter kocht gut.", "My mother cooks well."),
    "waschen":    ("Ich wasche meine Wäsche.", "I wash my laundry."),
    "fliegen":    ("Das Flugzeug fliegt hoch.", "The plane flies high."),
    "schwimmen":  ("Er schwimmt jeden Tag.", "He swims every day."),
    "tanzen":     ("Wir tanzen auf der Party.", "We dance at the party."),
    "singen":     ("Sie singt sehr schön.", "She sings very beautifully."),
    "gewinnen":   ("Wir wollen das Spiel gewinnen.", "We want to win the game."),
    "verlieren":  ("Er verliert immer seine Brille.", "He always loses his glasses."),
    "erklaeren":  ("Der Lehrer erklärt die Aufgabe.", "The teacher explains the task."),
    "besuchen":   ("Wir besuchen unsere Großeltern.", "We visit our grandparents."),
    "bezahlen":   ("Ich bezahle mit Karte.", "I pay by card."),
    "danken":     ("Ich danke dir sehr.", "Thank you very much."),
    "entscheiden":("Ich muss mich entscheiden.", "I need to decide."),
    "entwickeln": ("Die Firma entwickelt Apps.", "The company develops apps."),
    "erhalten":   ("Sie erhält viele Briefe.", "She receives many letters."),
    "erreichen":  ("Ich kann ihn nicht erreichen.", "I can't reach him."),
    "erzaehlen":  ("Er erzählt eine Geschichte.", "He tells a story."),
    "feiern":     ("Wir feiern Geburtstag.", "We're celebrating a birthday."),
    "fuehlen":    ("Ich fühle mich gut.", "I feel good."),
    "gefallen":   ("Das Buch gefällt mir.", "I like the book."),
    "gehoeren":   ("Das gehört mir.", "That belongs to me."),
    "hoffen":     ("Ich hoffe, es klappt.", "I hope it works out."),
    "kaempfen":   ("Er kämpft für seine Rechte.", "He fights for his rights."),
    "kosten":     ("Wie viel kostet das?", "How much does that cost?"),
    "lachen":     ("Sie lacht viel.", "She laughs a lot."),
    "lieben":     ("Ich liebe dich.", "I love you."),
    "moegen":     ("Ich mag Hunde.", "I like dogs."),
    "passieren":  ("Was ist passiert?", "What happened?"),
    "planen":     ("Wir planen einen Ausflug.", "We're planning a trip."),
    "reden":      ("Er redet zu viel.", "He talks too much."),
    "reisen":     ("Ich reise gern.", "I like to travel."),
    "schicken":   ("Ich schicke dir eine E-Mail.", "I'll send you an email."),
    "schmecken":  ("Das schmeckt sehr gut.", "That tastes very good."),
    "teilen":     ("Wir teilen die Pizza.", "We share the pizza."),
    "tragen":     ("Er trägt eine Jacke.", "He wears a jacket."),
    "versuchen":  ("Ich versuche es nochmal.", "I'll try again."),
    "waehlen":    ("Du musst einen wählen.", "You must choose one."),
    "wuenschen":  ("Ich wünsche dir viel Glück.", "I wish you good luck."),
    "aufmachen":  ("Mach die Tür auf!", "Open the door!"),
    "zumachen":   ("Bitte mach das Fenster zu.", "Please close the window."),
    "einladen":   ("Ich lade dich ein.", "I'm inviting you."),
    "aussteigen": ("Wir steigen hier aus.", "We get off here."),
    "einsteigen": ("Bitte einsteigen!", "Please board!"),
    "umsteigen":  ("Muss ich umsteigen?", "Do I need to change trains?"),
    "ankommen":   ("Der Zug kommt um fünf an.", "The train arrives at five."),
    "abfahren":   ("Der Bus fährt um acht ab.", "The bus departs at eight."),
    "aufstehen":  ("Ich stehe um sieben auf.", "I get up at seven."),
    "einschlafen":("Das Baby schläft schnell ein.", "The baby falls asleep quickly."),
    "aufwachen":  ("Ich wache früh auf.", "I wake up early."),
    "anrufen":    ("Ich rufe dich an.", "I'll call you."),
    "ausgehen":   ("Wir gehen heute Abend aus.", "We're going out tonight."),
    "einkaufen":  ("Sie geht jeden Samstag einkaufen.", "She goes shopping every Saturday."),
    "vorstellen": ("Ich stelle mich vor.", "I introduce myself."),
    "entschuldigen":("Entschuldige mich bitte.", "Please excuse me."),
    "bedeuten":   ("Was bedeutet dieses Wort?", "What does this word mean?"),
    "klingen":    ("Das klingt gut.", "That sounds good."),
    "scheinen":   ("Die Sonne scheint.", "The sun is shining."),
    "erscheinen": ("Das Buch erscheint morgen.", "The book is published tomorrow."),
    "verlassen":  ("Er verlässt das Haus.", "He leaves the house."),
    "treiben":    ("Er treibt viel Sport.", "He does a lot of sports."),
    "ziehen":     ("Wir ziehen nach München.", "We're moving to Munich."),
    "legen":      ("Leg das Buch auf den Tisch.", "Put the book on the table."),
    "stellen":    ("Ich stelle die Vase hier hin.", "I'll put the vase here."),
    "haengen":    ("Das Bild hängt an der Wand.", "The picture hangs on the wall."),
    "werfen":     ("Er wirft den Ball.", "He throws the ball."),
    "schneiden":  ("Sie schneidet das Brot.", "She cuts the bread."),
    "malen":      ("Das Kind malt ein Bild.", "The child paints a picture."),
    "bauen":      ("Sie bauen ein Haus.", "They're building a house."),
    "mieten":     ("Wir mieten eine Wohnung.", "We're renting an apartment."),
    "verkaufen":  ("Er verkauft sein Auto.", "He's selling his car."),
    "schliessen": ("Bitte schließ die Tür.", "Please close the door."),
    "druecken":   ("Drücke den Knopf.", "Press the button."),
    "stossen":    ("Er stößt gegen die Wand.", "He bumps into the wall."),
    "beruehren":  ("Berühr das nicht.", "Don't touch that."),
    "greifen":    ("Sie greift nach dem Glas.", "She reaches for the glass."),
    "packen":     ("Ich muss meinen Koffer packen.", "I need to pack my suitcase."),
    "heben":      ("Er hebt die Box hoch.", "He lifts the box."),
    "holen":      ("Kannst du Wasser holen?", "Can you fetch some water?"),
    "liefern":    ("Das Paket wird morgen geliefert.", "The package will be delivered tomorrow."),
    "empfangen":  ("Er empfängt seine Gäste.", "He receives his guests."),
    "wechseln":   ("Ich muss Geld wechseln.", "I need to exchange money."),
    "tauschen":   ("Können wir tauschen?", "Can we swap?"),
    "sparen":     ("Ich spare für ein neues Auto.", "I'm saving for a new car."),
    "ausgeben":   ("Er gibt zu viel Geld aus.", "He spends too much money."),
    "verdienen":  ("Sie verdient gut.", "She earns well."),
    "vorbereiten":("Ich bereite mich vor.", "I'm preparing myself."),
    "anmelden":   ("Ich melde mich an.", "I'm registering."),
    "abmelden":   ("Ich melde mich ab.", "I'm unsubscribing."),
    "bestellen":  ("Ich bestelle ein Wasser.", "I'll order a water."),
    "reservieren":("Ich reserviere einen Tisch.", "I'm reserving a table."),
    "empfehlen":  ("Können Sie etwas empfehlen?", "Can you recommend something?"),
    "erlauben":   ("Darf ich? – Ja, ich erlaube es.", "May I? – Yes, I allow it."),
    "verbieten":  ("Das ist verboten.", "That is forbidden."),
    "gelingen":   ("Es gelingt mir nicht.", "I don't manage to do it."),
    "scheitern":  ("Das Projekt scheitert.", "The project fails."),
    "verbessern": ("Ich muss mein Deutsch verbessern.", "I need to improve my German."),
    "wiederholen":("Kannst du das wiederholen?", "Can you repeat that?"),
    "aufhoeren":  ("Hör auf damit!", "Stop doing that!"),
    "anfangen":   ("Wann fangen wir an?", "When do we start?"),
    "weitermachen":("Mach weiter!", "Keep going!"),
    # nouns
    "mann":       ("Der Mann liest die Zeitung.", "The man reads the newspaper."),
    "frau":       ("Die Frau arbeitet im Büro.", "The woman works in the office."),
    "kind":       ("Das Kind spielt im Garten.", "The child plays in the garden."),
    "jahr":       ("Dieses Jahr fahre ich nach Italien.", "This year I'm going to Italy."),
    "zeit":       ("Hast du Zeit?", "Do you have time?"),
    "hand":       ("Er gibt mir die Hand.", "He shakes my hand."),
    "stadt":      ("Berlin ist eine große Stadt.", "Berlin is a big city."),
    "land":       ("Ich komme aus einem kleinen Land.", "I come from a small country."),
    "welt":       ("Die Welt ist groß.", "The world is big."),
    "tag":        ("Der Tag war lang.", "The day was long."),
    "haus":       ("Wir wohnen in einem alten Haus.", "We live in an old house."),
    "mensch":     ("Der Mensch braucht Wasser.", "A person needs water."),
    "arbeit":     ("Die Arbeit macht Spaß.", "The work is fun."),
    "leben":      ("Das Leben ist schön.", "Life is beautiful."),
    "wasser":     ("Ich trinke viel Wasser.", "I drink a lot of water."),
    "weg":        ("Welcher Weg führt zum Bahnhof?", "Which way leads to the station?"),
    "schule":     ("Die Kinder gehen zur Schule.", "The children go to school."),
    "auto":       ("Mein Auto ist rot.", "My car is red."),
    "geld":       ("Ich habe kein Geld.", "I have no money."),
    "essen_n":    ("Das Essen schmeckt gut.", "The food tastes good."),
    "buch":       ("Das Buch ist interessant.", "The book is interesting."),
    "tisch":      ("Das Essen steht auf dem Tisch.", "The food is on the table."),
    "stuhl":      ("Setz dich auf den Stuhl!", "Sit down on the chair!"),
    "tuer":       ("Die Tür ist offen.", "The door is open."),
    "fenster":    ("Das Fenster ist zu.", "The window is closed."),
    "bett":       ("Ich gehe ins Bett.", "I'm going to bed."),
    "boden":      ("Die Katze sitzt auf dem Boden.", "The cat sits on the floor."),
    "wand":       ("Das Bild hängt an der Wand.", "The picture is on the wall."),
    "familie":    ("Meine Familie ist groß.", "My family is big."),
    "mutter":     ("Meine Mutter kocht gut.", "My mother cooks well."),
    "vater":      ("Mein Vater arbeitet viel.", "My father works a lot."),
    "bruder":     ("Mein Bruder ist jünger als ich.", "My brother is younger than me."),
    "schwester":  ("Meine Schwester singt gut.", "My sister sings well."),
    "sohn":       ("Ihr Sohn ist acht Jahre alt.", "Her son is eight years old."),
    "tochter":    ("Ihre Tochter geht zur Schule.", "Her daughter goes to school."),
    "freund":     ("Mein Freund kommt morgen.", "My friend is coming tomorrow."),
    "freundin":   ("Meine Freundin wohnt in Hamburg.", "My girlfriend lives in Hamburg."),
    "lehrer":     ("Der Lehrer erklärt die Aufgabe.", "The teacher explains the task."),
    "schueler":   ("Der Schüler macht seine Hausaufgaben.", "The student does his homework."),
    "arzt":       ("Der Arzt kommt gleich.", "The doctor is coming soon."),
    "polizist":   ("Der Polizist hilft uns.", "The police officer helps us."),
    "firma":      ("Die Firma ist groß.", "The company is large."),
    "buero":      ("Er arbeitet im Büro.", "He works in the office."),
    "bahnhof":    ("Der Bahnhof ist weit.", "The station is far."),
    "flughafen":  ("Der Flughafen ist sehr groß.", "The airport is very big."),
    "hotel":      ("Das Hotel ist schön.", "The hotel is nice."),
    "restaurant": ("Das Restaurant ist teuer.", "The restaurant is expensive."),
    "geschaeft":  ("Das Geschäft ist geschlossen.", "The shop is closed."),
    "markt":      ("Ich gehe auf den Markt.", "I'm going to the market."),
    "strasse":    ("Die Straße ist breit.", "The street is wide."),
    "platz":      ("Der Platz ist groß.", "The square is big."),
    "park":       ("Wir gehen in den Park.", "We're going to the park."),
    "berg":       ("Der Berg ist sehr hoch.", "The mountain is very high."),
    "fluss":      ("Der Fluss ist breit.", "The river is wide."),
    "see":        ("Der See ist kalt.", "The lake is cold."),
    "meer":       ("Das Meer ist blau.", "The sea is blue."),
    "hund":       ("Der Hund ist groß.", "The dog is big."),
    "katze":      ("Die Katze schläft.", "The cat is sleeping."),
    "vogel":      ("Der Vogel singt.", "The bird sings."),
    "fisch":      ("Der Fisch schwimmt.", "The fish swims."),
    "pferd":      ("Das Pferd ist schnell.", "The horse is fast."),
    "kuh":        ("Die Kuh gibt Milch.", "The cow gives milk."),
    "schwein":    ("Das Schwein ist auf dem Bauernhof.", "The pig is on the farm."),
    "huhn":       ("Das Huhn legt Eier.", "The chicken lays eggs."),
    "brot":       ("Das Brot ist frisch.", "The bread is fresh."),
    "milch":      ("Ich trinke Milch.", "I drink milk."),
    "fleisch":    ("Er isst kein Fleisch.", "He doesn't eat meat."),
    "gemuese":    ("Gemüse ist gesund.", "Vegetables are healthy."),
    "obst":       ("Obst ist lecker.", "Fruit is tasty."),
    "apfel":      ("Der Apfel ist rot.", "The apple is red."),
    "kartoffel":  ("Die Kartoffel ist weich.", "The potato is soft."),
    "ei":         ("Ich esse ein Ei.", "I'm eating an egg."),
    "kaffee":     ("Ich trinke morgens Kaffee.", "I drink coffee in the morning."),
    "tee":        ("Sie trinkt Tee.", "She drinks tea."),
    "bier":       ("Er trinkt ein Bier.", "He drinks a beer."),
    "wein":       ("Wir trinken Wein.", "We drink wine."),
    "teller":     ("Der Teller ist leer.", "The plate is empty."),
    "glas":       ("Das Glas ist voll.", "The glass is full."),
    "flasche":    ("Die Flasche ist aus Glas.", "The bottle is made of glass."),
    "messer":     ("Das Messer ist scharf.", "The knife is sharp."),
    "gabel":      ("Die Gabel liegt neben dem Teller.", "The fork is next to the plate."),
    "loeffel":    ("Der Löffel ist im Joghurt.", "The spoon is in the yogurt."),
    "jacke":      ("Deine Jacke ist schön.", "Your jacket is nice."),
    "hose":       ("Die Hose ist zu groß.", "The trousers are too big."),
    "hemd":       ("Das Hemd ist weiß.", "The shirt is white."),
    "kleid":      ("Das Kleid ist rot.", "The dress is red."),
    "uhr":        ("Die Uhr hängt an der Wand.", "The clock is on the wall."),
    "telefon":    ("Das Telefon klingelt.", "The phone is ringing."),
    "computer":   ("Der Computer ist neu.", "The computer is new."),
    "schluessel": ("Ich habe meinen Schlüssel vergessen.", "I forgot my key."),
    "brief":      ("Ich schreibe einen Brief.", "I'm writing a letter."),
    "zeitung":    ("Er liest die Zeitung.", "He reads the newspaper."),
    "film":       ("Der Film ist interessant.", "The film is interesting."),
    "musik":      ("Ich höre gern Musik.", "I like listening to music."),
    "kunst":      ("Kunst ist schön.", "Art is beautiful."),
    "sport":      ("Sport ist gesund.", "Sport is healthy."),
    "spiel":      ("Das Spiel macht Spaß.", "The game is fun."),
    "ball":       ("Der Ball ist rund.", "The ball is round."),
    "farbe":      ("Welche Farbe magst du?", "What colour do you like?"),
    "licht":      ("Das Licht ist hell.", "The light is bright."),
    "stimme":     ("Ihre Stimme ist schön.", "Her voice is beautiful."),
    "frage":      ("Das ist eine gute Frage.", "That's a good question."),
    "antwort":    ("Ich weiß die Antwort nicht.", "I don't know the answer."),
    "problem":    ("Das ist kein Problem.", "That's no problem."),
    "loesung":    ("Wir finden eine Lösung.", "We'll find a solution."),
    "idee":       ("Das ist eine gute Idee.", "That's a good idea."),
    "meinung":    ("Was ist deine Meinung?", "What's your opinion?"),
    "nachricht":  ("Ich habe eine Nachricht.", "I have a message."),
    "geschichte": ("Er erzählt eine Geschichte.", "He tells a story."),
    "nummer":     ("Wie ist deine Nummer?", "What's your number?"),
    "name":       ("Wie ist dein Name?", "What's your name?"),
    "wort":       ("Ich kenne dieses Wort nicht.", "I don't know this word."),
    "satz":       ("Der Satz ist lang.", "The sentence is long."),
    "sprache":    ("Deutsch ist eine schwere Sprache.", "German is a difficult language."),
    "bild":       ("Das Bild ist schön.", "The picture is beautiful."),
    "foto":       ("Ich mache ein Foto.", "I'm taking a photo."),
    "karte":      ("Ich kaufe eine Karte.", "I'm buying a ticket."),
    "zimmer":     ("Das Zimmer ist sauber.", "The room is clean."),
    "kueche":     ("Die Küche ist modern.", "The kitchen is modern."),
    "bad":        ("Das Bad ist klein.", "The bathroom is small."),
    "garten":     ("Der Garten ist schön.", "The garden is beautiful."),
    "dorf":       ("Das Dorf ist klein.", "The village is small."),
    "insel":      ("Die Insel ist wunderschön.", "The island is beautiful."),
    "nacht":      ("Die Nacht ist kalt.", "The night is cold."),
    "morgen":     ("Guten Morgen!", "Good morning!"),
    "abend":      ("Guten Abend!", "Good evening!"),
    "woche":      ("Diese Woche bin ich beschäftigt.", "This week I'm busy."),
    "monat":      ("Im nächsten Monat fahre ich weg.", "Next month I'm going away."),
    "stunde":     ("Wir warten eine Stunde.", "We wait for an hour."),
    "minute":     ("Warte eine Minute!", "Wait a minute!"),
    "sekunde":    ("In einer Sekunde bin ich da.", "I'll be there in a second."),
    "koerper":    ("Der Körper braucht Ruhe.", "The body needs rest."),
    "kopf":       ("Mein Kopf tut weh.", "My head hurts."),
    "auge":       ("Sie hat blaue Augen.", "She has blue eyes."),
    "ohr":        ("Er hat große Ohren.", "He has big ears."),
    "nase":       ("Meine Nase ist rot.", "My nose is red."),
    "mund":       ("Der Mund ist trocken.", "The mouth is dry."),
    "zahn":       ("Der Zahn tut weh.", "The tooth hurts."),
    "haar":       ("Ihr Haar ist lang.", "Her hair is long."),
    "arm":        ("Mein Arm ist kaputt.", "My arm is broken."),
    "bein":       ("Das Bein tut weh.", "My leg hurts."),
    "herz":       ("Ihr Herz ist groß.", "Her heart is big."),
    "blut":       ("Das Blut ist rot.", "Blood is red."),
    "luft":       ("Die Luft ist frisch.", "The air is fresh."),
    "erde":       ("Die Erde ist rund.", "The earth is round."),
    "feuer":      ("Das Feuer ist warm.", "The fire is warm."),
    "energie":    ("Ich habe keine Energie.", "I have no energy."),
    "macht":      ("Wissen ist Macht.", "Knowledge is power."),
    "kraft":      ("Er hat viel Kraft.", "He has a lot of strength."),
    "freiheit":   ("Freiheit ist wichtig.", "Freedom is important."),
    "wahrheit":   ("Er sagt die Wahrheit.", "He tells the truth."),
    "liebe_n":    ("Liebe macht blind.", "Love is blind."),
    "freude":     ("Das ist eine große Freude.", "That is a great joy."),
    "angst":      ("Ich habe Angst.", "I'm afraid."),
    "hoffnung":   ("Es gibt immer Hoffnung.", "There is always hope."),
    "traum":      ("Das ist mein Traum.", "That's my dream."),
    "gedanke":    ("Das ist ein guter Gedanke.", "That's a good thought."),
    "gefuehl":    ("Ich habe ein gutes Gefühl.", "I have a good feeling."),
    "unterschied":("Was ist der Unterschied?", "What is the difference?"),
    "beispiel":   ("Zum Beispiel Äpfel.", "For example, apples."),
    "ergebnis":   ("Das Ergebnis ist gut.", "The result is good."),
    "moeglichkeit":("Das ist eine Möglichkeit.", "That is a possibility."),
    "aufgabe":    ("Das ist meine Aufgabe.", "That is my task."),
    "ziel":       ("Was ist dein Ziel?", "What is your goal?"),
    "erfolg":     ("Das ist ein großer Erfolg.", "That is a great success."),
    "fehler":     ("Jeder macht Fehler.", "Everyone makes mistakes."),
    "chance":     ("Das ist eine gute Chance.", "That's a good opportunity."),
    "risiko":     ("Es gibt ein Risiko.", "There is a risk."),
    "preis":      ("Der Preis ist hoch.", "The price is high."),
    "qualitaet":  ("Die Qualität ist gut.", "The quality is good."),
    "menge":      ("Das ist eine große Menge.", "That's a large quantity."),
    "linie":      ("Fahre die rote Linie.", "Take the red line."),
    "punkt":      ("Das ist ein wichtiger Punkt.", "That is an important point."),
    "form":       ("Welche Form hat es?", "What shape is it?"),
    "richtung":   ("In welche Richtung?", "In which direction?"),
    "entfernung": ("Die Entfernung ist groß.", "The distance is large."),
    "gewicht":    ("Das Gewicht ist drei Kilo.", "The weight is three kilos."),
    "groesse":    ("Welche Größe haben Sie?", "What size do you take?"),
    "gruppe":     ("Wir sind eine Gruppe.", "We are a group."),
    "teil":       ("Das ist ein Teil des Problems.", "That is part of the problem."),
    "stueck":     ("Ich nehme ein Stück Kuchen.", "I'll take a piece of cake."),
    "reihe":      ("Wir stehen in einer Reihe.", "We stand in a row."),
    "liste":      ("Ich habe eine Liste.", "I have a list."),
    "titel":      ("Was ist der Titel des Buches?", "What is the title of the book?"),
    "inhalt":     ("Der Inhalt ist interessant.", "The content is interesting."),
    "system":     ("Das System funktioniert.", "The system works."),
    "netz":       ("Das Netz ist schnell.", "The network is fast."),
    "programm":   ("Das Programm ist gut.", "The program is good."),
    "datei":      ("Die Datei ist groß.", "The file is large."),
    "seite":      ("Auf Seite drei.", "On page three."),
    "artikel":    ("Der Artikel ist interessant.", "The article is interesting."),
    "vertrag":    ("Er unterschreibt den Vertrag.", "He signs the contract."),
    "gesetz":     ("Das Gesetz ist klar.", "The law is clear."),
    "recht":      ("Das ist mein Recht.", "That is my right."),
    "pflicht":    ("Das ist meine Pflicht.", "That is my duty."),
    "regel":      ("Die Regel ist einfach.", "The rule is simple."),
    "methode":    ("Diese Methode ist besser.", "This method is better."),
    "plan":       ("Was ist der Plan?", "What is the plan?"),
    "projekt":    ("Das Projekt ist fertig.", "The project is finished."),
    "produkt":    ("Das Produkt ist neu.", "The product is new."),
    "marke":      ("Das ist eine gute Marke.", "That is a good brand."),
    "modell":     ("Das Modell ist modern.", "The model is modern."),
    "typ":        ("Er ist ein netter Typ.", "He is a nice guy."),
    "art":        ("Was für eine Art ist das?", "What kind is that?"),
    "weise":      ("Auf welche Weise?", "In what way?"),
    "stil":       ("Er hat Stil.", "He has style."),
    "schritt":    ("Das ist ein großer Schritt.", "That is a big step."),
    "phase":      ("Wir sind in einer neuen Phase.", "We are in a new phase."),
    "stufe":      ("Die erste Stufe ist fertig.", "The first stage is done."),
    "ebene":      ("Das ist eine andere Ebene.", "That is a different level."),
    "bereich":    ("In diesem Bereich.", "In this area."),
    "thema":      ("Was ist das Thema?", "What is the topic?"),
    "begriff":    ("Das ist ein neuer Begriff.", "That is a new term."),
    "text":       ("Lies den Text!", "Read the text!"),
}

# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------
def to_slug(word: str) -> str:
    w = word.lower()
    w = w.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    w = re.sub(r"[^a-z0-9]", "", w)
    return w

# ---------------------------------------------------------------------------
# Wiktionary batch fetch  (up to 50 titles per request)
# ---------------------------------------------------------------------------
API = "https://de.wiktionary.org/w/api.php"

def batch_fetch(titles: list[str]) -> dict[str, str]:
    """Return {title: wikitext} for each title that exists."""
    result = {}
    chunk_size = 40  # stay comfortably under the 50 limit
    for i in range(0, len(titles), chunk_size):
        chunk = titles[i:i+chunk_size]
        params = urllib.parse.urlencode({
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "format": "json",
            "titles": "|".join(chunk),
        })
        url = f"{API}?{params}"
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "DeutschFlashcard/1.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read())
                break
            except Exception as e:
                if attempt == 3:
                    print(f"  [WARN] batch fetch failed for chunk {i}: {e}", file=sys.stderr)
                    data = {}
                time.sleep(2 ** attempt)
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            revs = page.get("revisions", [])
            if revs:
                wikitext = revs[0].get("*") or revs[0].get("content", "")
                if wikitext:
                    result[title] = wikitext
        time.sleep(0.3)  # be polite to the API
    return result

# ---------------------------------------------------------------------------
# Parse genus + plural for a noun from German Wiktionary wikitext
# ---------------------------------------------------------------------------
def parse_noun(wikitext: str) -> tuple[str, str] | None:
    """Return (genus, plural) or None if not parseable."""
    # Find the German section
    de_section = re.search(r"==\s*[^=]*\({{Sprache\|Deutsch}}\)[^=]*==(.+?)(?:==\s*\w|\Z)",
                           wikitext, re.DOTALL)
    if not de_section:
        # Try simpler: just look for Wortart Substantiv
        if "Substantiv" not in wikitext:
            return None
        section = wikitext
    else:
        section = de_section.group(1)

    # Genus
    genus = None
    # {{Deutsch Substantiv Übersicht|Genus=m ...}} or |Genus 1=m
    m = re.search(r"\|Genus(?:\s*1)?\s*=\s*([mfn])", section)
    if m:
        g = m.group(1)
        genus = {"m": "der", "f": "die", "n": "das"}.get(g)
    if not genus:
        # fallback: look for |Genus=m anywhere
        m = re.search(r"Genus[^\|=\n]*=\s*([mfn])", section)
        if m:
            genus = {"m": "der", "f": "die", "n": "das"}.get(m.group(1))

    # Plural — look for Nominativ Plural
    plural = None
    # |Nominativ Plural=Hunde  or  |Nominativ Plural 1=Hunde
    m = re.search(r"\|Nominativ\s+Plural(?:\s+\d+)?\s*=\s*([^\|\n\}]+)", section)
    if m:
        pl = m.group(1).strip()
        if pl and pl not in ("-", "—", "kein Plural", "''kein Plural''"):
            plural = pl.strip("'")
        else:
            plural = None  # no plural form

    if genus and plural is not None:
        return genus, plural
    if genus:
        return genus, None  # genus found but no plural (uncountable)
    return None

# ---------------------------------------------------------------------------
# Parse verb forms from German Wiktionary wikitext
# ---------------------------------------------------------------------------
def parse_verb(wikitext: str) -> tuple[str, str, str, str] | None:
    """Return (pres3sg, praet, aux, partizip2) or None."""
    if "Verb" not in wikitext:
        return None

    # 3rd person singular present
    pres3 = None
    m = re.search(r"\|Präsens_er,\s*sie,\s*es\s*=\s*([^\|\n\}]+)", wikitext)
    if not m:
        m = re.search(r"\|Präsens_er[^\|=\n]*=\s*([^\|\n\}]+)", wikitext)
    if m:
        pres3 = m.group(1).strip().strip("'")

    # Präteritum (1st/3rd person singular)
    praet = None
    m = re.search(r"\|Präteritum_ich\s*=\s*([^\|\n\}]+)", wikitext)
    if not m:
        m = re.search(r"\|Präteritum_er[^\|=\n]*=\s*([^\|\n\}]+)", wikitext)
    if m:
        praet = m.group(1).strip().strip("'")

    # Auxiliary (haben/sein)
    aux = None
    m = re.search(r"\|Hilfsverb\s*=\s*(haben|sein)", wikitext, re.IGNORECASE)
    if m:
        aux = m.group(1).lower()

    # Partizip II
    pp = None
    m = re.search(r"\|Partizip\s*II\s*=\s*([^\|\n\}]+)", wikitext)
    if not m:
        m = re.search(r"\|Partizip_II\s*=\s*([^\|\n\}]+)", wikitext)
    if m:
        pp = m.group(1).strip().strip("'")

    if pres3 and praet and aux and pp:
        return pres3, praet, aux, pp
    return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    words_out = []
    skipped = []

    # Interleave verbs and nouns so each group has ~10 of each
    # Build candidate pairs: (word, kind) in frequency order
    candidates = []
    v_idx, n_idx = 0, 0
    while v_idx < len(VERBS) or n_idx < len(NOUNS):
        for _ in range(10):
            if v_idx < len(VERBS):
                candidates.append((VERBS[v_idx], "verb"))
                v_idx += 1
        for _ in range(10):
            if n_idx < len(NOUNS):
                candidates.append((NOUNS[n_idx], "noun"))
                n_idx += 1

    # Fetch all wikitext in batches
    print("Fetching wikitext from de.wiktionary.org …", file=sys.stderr)
    all_titles = [w for w, _ in candidates]
    wikitext_map = batch_fetch(all_titles)
    print(f"  Got wikitext for {len(wikitext_map)}/{len(all_titles)} titles", file=sys.stderr)

    # Process each candidate
    group = 1
    count_in_group = 0

    for word, kind in candidates:
        if len(words_out) >= 500:
            break

        wt = wikitext_map.get(word, "")
        slug = to_slug(word)

        # Avoid duplicate slugs
        existing_slugs = {w["id"] for w in words_out}

        if kind == "verb":
            parsed = parse_verb(wt) if wt else None
            if not parsed:
                skipped.append(f"VERB {word}: no wikitext or parse failed")
                continue
            pres3, praet, aux, pp = parsed
            forms = f"{pres3} · {praet} · {aux} {pp}"
            word_type = "verb"
            de_word = word
            # pick example
            ex_key = slug
            ex_de, ex_en = EXAMPLES.get(ex_key, (f"Ich kann {word}.", f"I can {word}."))
        else:
            parsed = parse_noun(wt) if wt else None
            if not parsed:
                skipped.append(f"NOUN {word}: no wikitext or parse failed")
                continue
            genus, plural = parsed
            word_type = genus  # "der"/"die"/"das"
            de_word = f"{genus} {word}"
            if plural:
                # Build "die Hunde" form
                article_pl = "die"
                forms = f"{article_pl} {plural}"
            else:
                forms = "kein Plural"
            ex_key = slug
            ex_de, ex_en = EXAMPLES.get(ex_key, (f"{genus} {word} ist hier.", f"The {word.lower()} is here."))

        # Unique slug
        if slug in existing_slugs:
            slug = slug + "_2"

        # Assign group
        if count_in_group >= 20:
            group += 1
            count_in_group = 0
        if group > 25:
            break

        entry = {
            "id": slug,
            "group": group,
            "type": word_type,
            "de": de_word,
            "en": "",  # filled below from a simple lookup
            "forms": forms,
            "example": ex_de,
            "exampleEn": ex_en,
        }
        words_out.append(entry)
        count_in_group += 1

    # Fill English meanings
    EN_MEANINGS = {
        "sein":"to be","haben":"to have","werden":"to become","können":"can / to be able to",
        "müssen":"must / to have to","sagen":"to say","machen":"to make / do","gehen":"to go",
        "kommen":"to come","wissen":"to know","sehen":"to see","lassen":"to let / leave",
        "stehen":"to stand","finden":"to find","bleiben":"to stay","liegen":"to lie / be located",
        "heißen":"to be called","denken":"to think","nehmen":"to take","tun":"to do",
        "glauben":"to believe","halten":"to hold / stop","nennen":"to name / call",
        "zeigen":"to show","führen":"to lead","arbeiten":"to work","spielen":"to play",
        "sprechen":"to speak","bringen":"to bring","leben":"to live","fahren":"to drive / travel",
        "fallen":"to fall","folgen":"to follow","geben":"to give","handeln":"to act / deal",
        "helfen":"to help","hören":"to hear / listen","kaufen":"to buy","kennen":"to know (person)",
        "laufen":"to run / walk","lesen":"to read","meinen":"to mean / think","öffnen":"to open",
        "schreiben":"to write","setzen":"to put / set","suchen":"to look for","treffen":"to meet",
        "warten":"to wait","essen":"to eat","trinken":"to drink","schlafen":"to sleep",
        "wohnen":"to live (somewhere)","lernen":"to learn","verstehen":"to understand",
        "fragen":"to ask","antworten":"to answer","beginnen":"to begin","brauchen":"to need",
        "vergessen":"to forget","erinnern":"to remember","sterben":"to die","wachsen":"to grow",
        "kochen":"to cook","waschen":"to wash","fliegen":"to fly","schwimmen":"to swim",
        "tanzen":"to dance","singen":"to sing","gewinnen":"to win","verlieren":"to lose",
        "erklären":"to explain","besuchen":"to visit","bezahlen":"to pay","danken":"to thank",
        "entscheiden":"to decide","entwickeln":"to develop","erhalten":"to receive",
        "erreichen":"to reach","erzählen":"to tell / narrate","feiern":"to celebrate",
        "fühlen":"to feel","gefallen":"to please / like","gehören":"to belong",
        "hoffen":"to hope","kämpfen":"to fight","kosten":"to cost","lachen":"to laugh",
        "lieben":"to love","mögen":"to like","passieren":"to happen","planen":"to plan",
        "reden":"to talk","reisen":"to travel","schicken":"to send","schmecken":"to taste",
        "teilen":"to share","tragen":"to wear / carry","versuchen":"to try","wählen":"to choose",
        "wünschen":"to wish","aufmachen":"to open","zumachen":"to close","einladen":"to invite",
        "aussteigen":"to get off","einsteigen":"to get on","umsteigen":"to change (transport)",
        "ankommen":"to arrive","abfahren":"to depart","aufstehen":"to get up",
        "einschlafen":"to fall asleep","aufwachen":"to wake up","anrufen":"to call (phone)",
        "ausgehen":"to go out","einkaufen":"to go shopping","vorstellen":"to introduce",
        "entschuldigen":"to excuse / apologise","bedeuten":"to mean","klingen":"to sound",
        "scheinen":"to seem / shine","erscheinen":"to appear","verlassen":"to leave",
        "treiben":"to do (sport)","ziehen":"to pull / move","legen":"to lay / put",
        "stellen":"to put (upright)","hängen":"to hang","werfen":"to throw",
        "schneiden":"to cut","malen":"to paint","bauen":"to build","mieten":"to rent",
        "verkaufen":"to sell","schließen":"to close","drücken":"to press","stoßen":"to push",
        "berühren":"to touch","greifen":"to grasp","packen":"to pack","heben":"to lift",
        "holen":"to fetch","liefern":"to deliver","empfangen":"to receive","wechseln":"to change",
        "tauschen":"to swap",
        "Mann":"man","Frau":"woman","Kind":"child","Jahr":"year","Zeit":"time","Hand":"hand",
        "Stadt":"city","Land":"country","Welt":"world","Tag":"day","Haus":"house",
        "Mensch":"person / human","Arbeit":"work","Leben":"life","Wasser":"water","Weg":"way / path",
        "Schule":"school","Auto":"car","Geld":"money","Essen":"food","Buch":"book","Tisch":"table",
        "Stuhl":"chair","Tür":"door","Fenster":"window","Bett":"bed","Boden":"floor / ground",
        "Wand":"wall","Familie":"family","Mutter":"mother","Vater":"father","Bruder":"brother",
        "Schwester":"sister","Sohn":"son","Tochter":"daughter","Freund":"friend / boyfriend",
        "Freundin":"friend / girlfriend","Lehrer":"teacher","Schüler":"student / pupil",
        "Arzt":"doctor","Polizist":"police officer","Firma":"company","Büro":"office",
        "Bahnhof":"train station","Flughafen":"airport","Hotel":"hotel","Restaurant":"restaurant",
        "Geschäft":"shop / business","Markt":"market","Straße":"street","Platz":"square / place",
        "Park":"park","Berg":"mountain","Fluss":"river","See":"lake","Meer":"sea",
        "Hund":"dog","Katze":"cat","Vogel":"bird","Fisch":"fish","Pferd":"horse","Kuh":"cow",
        "Schwein":"pig","Huhn":"chicken","Brot":"bread","Milch":"milk","Fleisch":"meat",
        "Gemüse":"vegetables","Obst":"fruit","Apfel":"apple","Kartoffel":"potato","Ei":"egg",
        "Kaffee":"coffee","Tee":"tea","Bier":"beer","Wein":"wine","Teller":"plate",
        "Glas":"glass","Flasche":"bottle","Messer":"knife","Gabel":"fork","Löffel":"spoon",
        "Jacke":"jacket","Hose":"trousers","Hemd":"shirt","Kleid":"dress","Uhr":"clock / watch",
        "Telefon":"telephone","Computer":"computer","Schlüssel":"key","Brief":"letter",
        "Zeitung":"newspaper","Film":"film","Musik":"music","Kunst":"art","Sport":"sport",
        "Spiel":"game","Ball":"ball","Farbe":"colour","Licht":"light","Stimme":"voice",
        "Frage":"question","Antwort":"answer","Problem":"problem","Lösung":"solution",
        "Idee":"idea","Meinung":"opinion","Nachricht":"message / news","Geschichte":"story / history",
        "Nummer":"number","Name":"name","Wort":"word","Satz":"sentence","Sprache":"language",
        "Bild":"picture / image","Foto":"photo","Karte":"card / map / ticket","Zimmer":"room",
        "Küche":"kitchen","Bad":"bathroom","Garten":"garden","Dorf":"village","Insel":"island",
        "Nacht":"night","Morgen":"morning","Abend":"evening","Woche":"week","Monat":"month",
        "Stunde":"hour","Minute":"minute","Sekunde":"second","Körper":"body","Kopf":"head",
        "Auge":"eye","Ohr":"ear","Nase":"nose","Mund":"mouth","Zahn":"tooth","Haar":"hair",
        "Arm":"arm","Bein":"leg","Herz":"heart","Blut":"blood","Luft":"air","Erde":"earth",
        "Feuer":"fire","Energie":"energy","Macht":"power","Kraft":"strength / power",
        "Freiheit":"freedom","Wahrheit":"truth","Liebe":"love","Freude":"joy","Angst":"fear",
        "Hoffnung":"hope","Traum":"dream","Gedanke":"thought","Gefühl":"feeling",
        "Unterschied":"difference","Beispiel":"example","Ergebnis":"result",
        "Möglichkeit":"possibility","Aufgabe":"task","Ziel":"goal","Erfolg":"success",
        "Fehler":"mistake","Chance":"chance","Risiko":"risk","Preis":"price","Qualität":"quality",
        "Menge":"quantity / amount","Linie":"line","Punkt":"point","Form":"form / shape",
        "Richtung":"direction","Entfernung":"distance","Gewicht":"weight","Größe":"size",
        "Gruppe":"group","Teil":"part","Stück":"piece","Reihe":"row / series","Liste":"list",
        "Titel":"title","Inhalt":"content","System":"system","Netz":"network","Programm":"programme",
        "Datei":"file","Seite":"page / side","Artikel":"article","Vertrag":"contract",
        "Gesetz":"law","Recht":"right / law","Pflicht":"duty","Regel":"rule","Methode":"method",
        "Plan":"plan","Projekt":"project","Produkt":"product","Marke":"brand","Modell":"model",
        "Typ":"type / guy","Art":"type / kind","Weise":"way / manner","Stil":"style",
        "Schritt":"step","Phase":"phase","Stufe":"level / stage","Ebene":"level / plane",
        "Bereich":"area / field","Thema":"topic","Begriff":"term / concept","Text":"text",
        # new verbs
        "sparen":"to save (money)","ausgeben":"to spend","verdienen":"to earn",
        "vorbereiten":"to prepare","anmelden":"to register","abmelden":"to unsubscribe",
        "bestellen":"to order","reservieren":"to reserve","empfehlen":"to recommend",
        "erlauben":"to allow","verbieten":"to forbid","gelingen":"to succeed",
        "scheitern":"to fail","verbessern":"to improve","wiederholen":"to repeat",
        "aufhören":"to stop","anfangen":"to start","weitermachen":"to continue",
        "benutzen":"to use","verwenden":"to use / employ","ersetzen":"to replace",
        "hinzufügen":"to add","entfernen":"to remove","prüfen":"to check / test",
        "testen":"to test","messen":"to measure","zählen":"to count",
        "berechnen":"to calculate","vergleichen":"to compare","beschreiben":"to describe",
        "überprüfen":"to verify / check","analysieren":"to analyse",
        "organisieren":"to organise","kommunizieren":"to communicate",
        "diskutieren":"to discuss","zustimmen":"to agree","ablehnen":"to decline",
        "akzeptieren":"to accept","aufnehmen":"to record / take up",
        "aufzeichnen":"to record","veröffentlichen":"to publish","drucken":"to print",
        "speichern":"to save (file)","laden":"to load / charge","installieren":"to install",
        # new nouns
        "Wohnung":"flat / apartment","Brücke":"bridge","Kirche":"church",
        "Krankenhaus":"hospital","Apotheke":"pharmacy","Bibliothek":"library",
        "Museum":"museum","Kino":"cinema","Theater":"theatre","Konzert":"concert",
        "Veranstaltung":"event","Feier":"celebration","Urlaub":"holiday",
        "Reise":"trip / journey","Gepäck":"luggage","Koffer":"suitcase","Pass":"passport",
        "Visum":"visa","Ticket":"ticket","Fahrkarte":"train ticket","Fahrt":"journey / ride",
        "Strecke":"route / distance","Entscheidung":"decision","Wahl":"choice / election",
        "Gelegenheit":"opportunity","Einladung":"invitation","Besuch":"visit",
        "Gespräch":"conversation","Interview":"interview","Bericht":"report",
        "Aufsatz":"essay","Kommentar":"comment","Anfrage":"request / enquiry",
        "Angebot":"offer","Bestellung":"order","Rechnung":"bill / invoice",
        "Quittung":"receipt","Versicherung":"insurance","Steuer":"tax",
        "Konto":"account","Kredit":"credit / loan","Schuld":"debt / fault",
        "Gehalt":"salary","Lohn":"wage","Beruf":"profession","Stelle":"position / job",
        "Bewerbung":"application","Ausbildung":"training / education",
        "Studium":"university studies","Prüfung":"exam","Note":"grade",
        "Unterricht":"lesson / teaching","Übung":"exercise","Hausaufgabe":"homework",
        "Lektion":"lesson","Kapitel":"chapter","Abschnitt":"section","Absatz":"paragraph",
        "Zeile":"line","Zeichen":"character / sign","Symbol":"symbol",
        "Muster":"pattern","Design":"design","Layout":"layout","Format":"format",
        "Maßstab":"scale","Gewinn":"profit / win","Verlust":"loss",
        "Umsatz":"turnover","Kosten":"costs","Ausgabe":"expenditure","Einnahme":"income",
        "Ersparnis":"saving","Werkzeug":"tool","Maschine":"machine","Gerät":"device",
        "Apparat":"apparatus","Instrument":"instrument","Material":"material",
        "Stoff":"fabric / material","Holz":"wood","Metall":"metal",
        "Plastik":"plastic","Stein":"stone","Sand":"sand",
    }

    for entry in words_out:
        # Match by the base word (without article for nouns)
        de = entry["de"]
        base = de.split(" ", 1)[-1] if entry["type"] in ("der","die","das") else de
        entry["en"] = EN_MEANINGS.get(base, EN_MEANINGS.get(de, f"(see {base})"))

    # Write output
    out_path = "/home/user/German/words.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(words_out, f, ensure_ascii=False, indent=2)

    print(f"\n=== DONE: {len(words_out)} words written to {out_path} ===", file=sys.stderr)
    if skipped:
        print(f"\n=== SKIPPED ({len(skipped)}) ===", file=sys.stderr)
        for s in skipped:
            print(f"  {s}", file=sys.stderr)
    else:
        print("No words skipped.", file=sys.stderr)

if __name__ == "__main__":
    main()
