# Lærte lektier — Command Center (Chatoverblik)

Projekt-specifikke fælder. Globalt relevante lektier kopieres også til
`Masterversioner/context/05_lessons.md`.

---

## En Map bygget fra en sorteret liste arver rækkefølgen fra det SIDSTE sorteringstrin

**Problem:** Projektlisten på forsiden stod i forkert rækkefølge, selvom
"Senest aktive" var valgt. Kristians mentor — brugt samme dag og hele den
foregående uge — lå på 4. plads, mens MacGameBridge (ikke rørt i en uge) lå
nr. 3. Samme symptom inde i en projektgruppe: en chat fra 4 uger siden lå
over en fra 1 minut siden.

**Årsag:** `filterAndSort()` sorterer korrekt efter nyhed, men kører DEREFTER
et sidste, separat sorteringstrin der løfter pinnede chats (★) til toppen.
`renderGrid()` grupperede så efter projekt med `new Map()` — og en Map
bevarer insertion-order. Grupperne blev dermed oprettet i den rækkefølge
deres første chat optrådte, altså efter pin-løftet. Tre gamle pinnede chats
(Chatoverblik 22/6, Generelle spørgsmål 18/6, MacGameBridge 9/6) trak hele
deres projekt op i toppen. Pin-løftet var designet til at gælde *inde i* en
gruppe, men fik utilsigtet lov at bestemme rækkefølgen *mellem* grupperne.

**Fix:** Notér hver chats plads i rækkefølgen FØR pin-løftet (`s._order = i`),
og sortér grupperne efter den laveste `_order` i gruppen — ikke efter Map'ets
insertion-order:

```js
// i filterAndSort(), lige før pin-sorteringen:
xs.forEach((s, i) => { s._order = i; });

// i renderGrid(), efter grupperne er bygget:
const groupRank = new Map();
for (const [proj, items] of groups) {
  groupRank.set(proj, Math.min(...items.map(s => s._order ?? Infinity)));
}
const orderedGroups = [...groups.entries()]
  .sort((a, b) => groupRank.get(a[0]) - groupRank.get(b[0]));
```

Fordi rangeringen aflæses af den allerede sorterede liste og ikke af et
hårdkodet tidsstempel, følger gruppe-rækkefølgen automatisk med, uanset hvilken
sortering brugeren vælger (nyeste/ældste/oprettet) og uanset søge-tiers.

**Dato:** 2026-07-21

---

## Verificér frontend-sortering mod ægte data — ikke mod kodelæsning

**Problem:** Sorteringsfejlen ovenfor var usynlig ved at læse koden; hvert
enkelt sorteringstrin så korrekt ud isoleret. Det var samspillet mellem dem
der var forkert.

**Årsag:** Rækkefølgefejl viser sig først når man ser den faktiske rækkefølge
på faktiske data. Samme proces-hul som B1 (CSP-testen tjekkede kun CSP-teksten,
ikke at appen kørte under den).

**Fix:** Hent rådata fra det kørende endpoint (`curl localhost:7777/api/sessions`),
klip de RIGTIGE funktioner ud af `index.html` med `sed` på linjenumre, og
`eval` dem i Node med en minimal `state`-stub. Så testes den kode der faktisk
er i filen — ikke en genskrivning der kan indeholde de samme fejl som
udviklerens forståelse. Erstatter ikke Kristians egen browser-bekræftelse
til sidst, men fanger fejlen før den vises frem.

Én fælde i stub'en: `state.selectedCwd` skal være `""`, ikke `null` — koden
tester `!== ""`, så `null` filtrerer alt væk og giver et falsk "0 chats".

**Dato:** 2026-07-21
