# Åbningsprompt: plan for projekt-dashboard ("Status på mine projekter")

> Skrevet af Fable 5, 2026-07-02. Kopiér teksten herunder ind som første besked
> i en ny Opus-chat i `Chatoverblik/`-mappen. Skitsen ligger i
> `Chatoverblik/dashboard-skitse.jpg`.

---

Du er Opus. Implementér ikke — det her er en plan-session.

**Idéen (Kristians):** Et visuelt dashboard over alle projekter i
Masterversioner. Hvert projekt får et card med statuslamper (rød/gul/grøn)
for kædens trin: lokalt ændret → committet → pushet → deployet. Se min skitse:
`Chatoverblik/dashboard-skitse.jpg`. Formålet er at automatisere to ting fra
repo-politikken: "Mistet Mac"-testen (hvor ligger kopien af hver mappe?) og
overblikket over hvad der mangler commit/push/deploy — det jeg i dag kun får
ved at bede en AI grave med git-kommandoer.

**Beslutning der allerede er truffet (Fable, 2026-07-02):** Dashboardet bygges
som en del af Command Center (Chatoverblik) — IKKE som selvstændigt projekt —
fordi browseren ikke selv kan køre git, og Chatoverbliks lokale server allerede
kører og kender Masterversioner-mappen. Udfordr gerne beslutningen hvis du ser
et hul, men sig det FØR du skriver planen.

**Læs først (kun disse):**
- `Chatoverblik/STATUS.md` + evt. LESSONS.md
- `Chatoverblik/dashboard-skitse.jpg`
- `fable/repo-politik-udkast-2026-06-11.md` — afsnittene "Regel 0" og
  "Selvtjek" (hvis `context/08_repo_politik.md` findes, så brug den i stedet)
- `context/05_lessons.md` — især TCC-lektien (Documents/-mappen og
  baggrundsprocesser) og Safari Web App-cache-lektien; begge har ramt
  Chatoverblik før

**Lever:**

1. **Lampe-datamodel** — præcis definition pr. lampe: hvornår er den
   rød/gul/grøn, og hvad måles den mod (fx: committet = ingen ændrede filer;
   pushet = 0 commits foran origin; deployet = ?). Skitsen har 5 lamper
   inkl. en "xxxx"-placeholder og en "lokalt"-lampe — foreslå det endelige
   sæt, maks 5. Afklar også: hvordan opdages "deployet" (Cloudflare-opslag,
   wrangler, eller manuelt felt i projektets STATUS.md)? Vælg én kilde og
   begrund.
2. **Kanten af scope** — hvilke mapper vises? (Alle i Masterversioner, kun
   dem med STATUS.md, kun dem med .git?) Nested repos og root-repoet skal
   begge håndteres. Én regel, ingen specialtilfælde.
3. **De 3 største risici** — tekniske OG adfærdsmæssige (fx: dashboardet
   viser grønt på noget der reelt ikke er sikret).
4. **Trinvis plan til Sonnet** — små trin, ingen egne arkitektur- eller
   scope-valg, ét trin ad gangen.
5. **Acceptkriterier Kristian selv kan teste i browseren** — fx "lav en
   ændring i en testmappe uden at committe → kortet skifter til rød inden
   for X sekunder".

**Begrænsninger:** Ingen kompliment-runde. Hvis du mangler viden om
Chatoverbliks server-API, så læs koden målrettet (grep) i stedet for at gætte
— og sig eksplicit hvor du er usikker. Ingen eksterne services uden
pris-/vilkårstjek (regel 18).

**Denne chat er færdig når:** planen ligger som fil i `Chatoverblik/`
(fx `dashboard-plan.md`), committet til projektets repo, og Kristian ved
hvad Sonnet-chattens første trin er.
