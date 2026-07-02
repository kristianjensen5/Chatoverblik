# Plan: Projekt-dashboard "Status på mine projekter"

> Skrevet af Opus, 2026-07-02. Plan-session — intet er bygget endnu.
> Bygges ind i Command Center (Chatoverblik) som næste skridt via en Sonnet-chat.
> Skitse: `dashboard-skitse.jpg`. Åbningsprompt: `dashboard-plan-prompt.md`.

---

## 0. Beslutningen om at bygge i Command Center — godkendt, med ét forbehold

Fables beslutning holder: browseren kan ikke selv køre git, Command Center-serveren
kører allerede lokalt, kender `MASTERVERSIONER_ROOT`, bruger allerede `subprocess`
(`logged_popen`), har allerede sikkerhedslag (`_is_external`, `_is_csrf`, path-validering)
og har allerede URL-scanning (`scan_project_urls`) der kan genbruges til deploy-lampen.
Intet hul stort nok til at bygge separat.

**Forbeholdet (bliver til risiko 2 og et plan-trin):** git-opslag på 66 mapper må
IKKE ligge på den eksisterende 4-sekunders-polling. Det ville gøre hele appen langsom.
Git-status skal være et separat, on-demand endpoint med egen cache. Ikke en grund til
at bygge andetsteds — bare et krav til hvordan.

**Verificeret mod virkeligheden (ikke gæt):**
- `MASTERVERSIONER_ROOT = HERE.parent` (chatoverblik.py:36) — serveren kender rodmappen.
- 66 mapper på ét niveau i Masterversioner; ca. halvdelen har `.git`, halvdelen ikke.
- `build_projects_index` (chatoverblik.py:621) udleder projekter **fra chats** — kun mapper
  med en chat optræder. Dashboardet må derfor IKKE genbruge den liste; det skal
  enumerere filsystemet (som `/api/all-folders`, chatoverblik.py:1606).
- Alle git-kommandoer nedenfor er kørt mod det virkelige Chatoverblik-repo og giver
  det forventede output.

---

## 1. Lampe-datamodel

### Skitsen havde en redundans jeg har fjernet

Skitsens fem felter var `deployed | xxxx | pushed | commited | lokalt`. Men **"lokalt ændret"
og "committet" er to ender af samme fakta** (er arbejdstræet beskidt eller rent?) — to
lamper for ét spørgsmål. Jeg slår dem sammen til én ("Ændringer") og bruger de to frigjorte
pladser (den sammenlagte + "xxxx") på de to ting du faktisk vil automatisere fra
repo-politikken: **er der overhovedet en kopi uden for Mac'en** ("Mistet Mac"-testen) og
**er STATUS.md frisk**.

### De 5 lamper (venstre → højre på kortet)

Hver lampe er ét spørgsmål med tre tilstande. **Grå = "ikke relevant for denne mappe"** —
en bevidst fjerde tilstand, så vi aldrig viser grønt (eller rødt) på noget der ikke gælder.

| # | Lampe | 🟢 Grøn | 🟡 Gul | 🔴 Rød | ⚪ Grå (n/a) |
|---|---|---|---|---|---|
| 1 | **Sikret** (Mistet-Mac) | Repo har et remote → kopi på GitHub | Repo uden remote → git-historik, men kun lokalt | Ingen `.git` overhovedet → helt usikret | — (altid relevant) |
| 2 | **Ændringer** | Arbejdstræ rent — alt committet | Ucommittede ændringer ligger lokalt | — | Ikke et repo |
| 3 | **Pushet** | 0 commits foran sidst-kendte remote | Commits foran remote (ikke pushet) | — | Intet remote/upstream |
| 4 | **Deployet** | `deployed`-tag peger på HEAD → nyeste kode er live | Tag findes, men HEAD er foran → live er forældet | Live-URL findes, men aldrig deploy-registreret | Ingen live-URL → ikke et deploy-projekt |
| 5 | **STATUS.md** | Findes + "Senest opdateret" < 30 dage | Findes, men gammel/uden læsbar dato | Ingen STATUS.md | — (altid relevant) |

Lampe 5 er den blødeste — den understøtter STATUS-disciplinen (regel 5/6) og
repo-politikkens minimumskrav. **Bekræftet med (Kristian, 2026-07-02): den er
med.** Den hænger sammen med Mistet-Mac-testen: testen bygger på, at "bevidst
kun lokalt" står *i* STATUS.md — mangler filen, kan man ikke skelne "usikret ved
en fejl" fra "bevidst lokalt".

> **Note om lampesættet:** de fem lamper i skitsen var Kristians løse idé-skitse,
> ikke et facit. Sættet ovenfor er bygget op fra bunden ud fra to krav — "kan det
> måles pålideligt uden netværk?" og "svarer det på Mistet-Mac eller commit/push/
> deploy?" — og bekræftet af Kristian 2026-07-02.

### Præcis måling (git-kommandoer, alle verificeret)

For hver mappe `F` kører serveren (ingen netværk — se risiko 3):

```
git -C F rev-parse --show-toplevel          # er F sit EGET repo? (skal == F)
git -C F status --porcelain                 # ikke-tom = ucommittede ændringer
git -C F remote                             # tom = intet remote  → lampe 1 gul, lampe 3 grå
git -C F rev-parse --abbrev-ref @{u}        # fejler = intet upstream → lampe 3 grå
git -C F rev-list --left-right --count @{u}...HEAD   # "behind<TAB>ahead"; ahead>0 = ikke pushet
git -C F tag --points-at HEAD               # indeholder "deployed"? → lampe 4 grøn
git -C F rev-list -n1 deployed              # findes tag'et men ikke på HEAD? → lampe 4 gul
```
Lampe 4's "live-URL findes" genbruger `scan_project_urls(F)` (chatoverblik.py:519) —
den finder allerede `.pages.dev` / `.workers.dev` / `politiken.dk` fra wrangler.toml,
.git/config og .md-filer.

### Deploy-kilde: git-tag `deployed` — ét valg, begrundet

Jeg vælger **et git-tag ved navn `deployed`** som eneste kilde til deploy-lampen —
ikke Cloudflare-API, ikke wrangler-opslag, ikke live HTTP-tjek.

**Hvorfor ikke de andre:**
- **Cloudflare-API / wrangler:** ekstern afhængighed (regel 18: kræver auth-token, netværk,
  kan hænge/rate-limite), og — vigtigst — den kan alligevel ikke billigt svare på det
  spørgsmål der betyder noget: *"matcher den live version min lokale kode?"* Den kan kun
  sige "der ligger noget derude".
- **Live HTTP-tjek (HEAD på URL'en):** siger kun at siden *svarer*, ikke at den svarer med
  *din nyeste kode*. Det ville lyse grønt selv når du har un-deployet arbejde liggende — den
  farligste type falsk tryghed (se risiko 1).

**Hvorfor tag'et vinder:** det er den eneste kilde der binder "deployet" til en **konkret
commit**, så vi kan skelne "nyeste er live" (grøn) fra "deployet, men nyere arbejde ikke live"
(gul). Ingen ekstern service, virker offline, reproducerbart.

**Prisen (ærligt):** noget skal *sætte* tag'et efter et vellykket deploy. Indtil deploy-flowet
(`/luk`-skillen) gør det, viser lampe 4 rødt for alle deploy-projekter — hvilket faktisk er
korrekt: vi *har* ingen deploy-registrering endnu. Et lille ekstra trin i `/luk` (efter
`wrangler ... --branch=main` lykkes: `git tag -f deployed HEAD`) lukker hullet. Det trin ligger
i planen som et separat, valgfrit sidste trin — v1 af dashboardet fungerer uden det (deploy-lampen
er bare ærligt rød/grå indtil da).

### Fase 2 (bekræftet vej, ikke v1): Cloudflare-API som ægte-live-bekræftelse

Git-tag'et er din *hensigt* ("jeg deployede HEAD"). Cloudflares API er *sandheden* (hvad der
faktisk ligger live). Serveren *kan* spørge Cloudflare — samme mønster som det eksisterende
Anthropic-kald (`urllib` + token fra `.env`, `call_anthropic` chatoverblik.py:75-97). API'et
returnerer den commit der ligger live for et Pages-projekt, som vi sammenligner med HEAD →
grøn = *bekræftet* live == din kode.

**Hvorfor fase 2 og ikke v1 (Kristians valg 2026-07-02):**
- Dækker kun **6 af 66 mapper** — kun 6 har `wrangler.toml`. Resten (politiken.dk-CMS-embeds,
  github.io, ikke-deploy) kan API'et intet sige om; de forbliver på tag/grå.
- **Netværksafhængigt** — mister git-lampernes offline-egenskab; skal timeoute pænt til grå
  på VPN/offline.
- **Kræver stadig deploy-disciplin** — Cloudflare kender kun den live commit hvis deployet sendte
  den med (`wrangler pages deploy --commit-hash=$(git rev-parse HEAD)`). Bytter altså bare
  "sæt tag" ud med "send commit-hash med". Samme mængde disciplin.
- **Pris/vilkår (regel 18):** gratis på egen Cloudflare-konto; rate limit 1200/5 min irrelevant
  ved 6 projekter. Token gemmes i `.env` (allerede gitignored).

Fase 2 lægges *oven på* tag-lampen for de 6 Pages-projekter — den erstatter den ikke. Ligger som
sidste, separat trin i planen.

---

## 2. Scope — én regel

**Reglen:** Vis ét kort pr. **umiddelbar undermappe i Masterversioner** (ét niveau), minus
en fast infrastruktur-skipliste. Root-repoet (Masterversioner selv) får ét kort øverst.

- **Ikke** "kun mapper med .git" — det ville skjule præcis de mapper der er mest i fare
  (nogit-mapperne er hele pointen med Mistet-Mac-testen; de skal lyse rødt, ikke forsvinde).
- **Ikke** "kun mapper med STATUS.md" — samme problem.
- **Ikke** den chat-udledte projektliste (`build_projects_index`) — den mangler mapper uden chats.

Kilden er samme mønster som `/api/all-folders` (chatoverblik.py:1606) med samme skipliste
(`node_modules`, `__pycache__`, `.wrangler`, `Chatoverblik-dist`, `cloudflare-backup-*`,
dotmapper). **Bekræftet tilføjelse til skiplisten (Kristian, 2026-07-02):** `_archive`,
`Backups`, `context`, `fable` skjules — ren AI-infrastruktur, ikke projekter.

**Nested repos vs. root:** hvert kort kører git mod *sin egen* mappe
(`git -C F rev-parse --show-toplevel`). Er `F` sit eget repo → mål mod det. Har `F` ingen egen
`.git` → lampe 1 rød ("ikke sikret"), lamperne 2-4 grå. (Root-`.gitignore` holder alligevel
undermapperne ude af root-repoet, så en nogit-mappe *er* reelt usikret — det er den rigtige
alarm.) Root-repoet er ét kort der måles mod `MASTERVERSIONER_ROOT` selv.

---

## 3. De 3 største risici

1. **Adfærdsmæssig — falsk grønt / falsk tryghed.** Hvis en lampe defaulter til grøn når vi er
   i tvivl, stoler du på et kort der lyver. Konkret farligst: en deploy-lampe der lyser grønt
   fordi siden *svarer*, mens din nyeste kode ikke er deployet.
   **Modtræk:** deploy bindes til commit (tag), ingen live-tjek. Fjerde tilstand "grå = n/a"
   findes eksplicit, så vi aldrig maler grønt på det uafklarede. Default ved fejl/tvivl er grå
   eller rød — aldrig grøn.

2. **Teknisk — 66 git-kald blokerer appen.** Kører git-status synkront på hver af de ~4-sekunders
   polls, bliver hele Command Center langsomt, og et hængende git-kald (fx et beskadiget repo)
   kan blokere en server-tråd.
   **Modtræk:** separat `/api/repo-status`-endpoint der kun kører on-demand (når du åbner
   dashboardet + en ↻-knap), med `subprocess.run(..., timeout=5)` pr. kommando og en kort
   in-memory cache (fx 60 sek.). Aldrig på polling-stien.

3. **Teknisk/adfærdsmæssig — "Pushet"-lampen kan lyve uden fetch, + TCC.** `@{u}..HEAD`
   sammenligner mod den *lokalt kendte* remote-position, ikke mod GitHub live. Har du pushet fra
   en anden maskine, ved din Mac det ikke. For Mistet-Mac-formålet ("er MIT lokale arbejde nået
   ud?") er det korrekt nok — men kortet må sige "mod sidst-kendte remote", ikke foregive et
   live GitHub-opslag. **Vi laver bevidst ingen `git fetch`** (netværk, langsomt, hænger på VPN/
   offline). Desuden TCC-lektien: serveren læser `~/Documents/` fint fordi den startes manuelt
   via Terminal/VS Code (Full Disk Access) — men gøres den nogensinde til en LaunchAgent, dør
   git-kaldene stille (exit 78). Skriv det i koden som en kommentar.

---

## 4. Trinvis plan til Sonnet

Små trin, ét ad gangen, commit efter hvert. Ingen arkitektur- eller scope-valg for Sonnet —
alt er afgjort ovenfor.

1. **Backend-helper `git_status_for(folder)`** i chatoverblik.py: kører de 6 git-kommandoer via
   `subprocess.run(timeout=5)`, returnerer en dict med de 5 lampers tilstand
   (`green|yellow|red|gray`) + rådata (ahead-count, dirty-bool, remote-URL). Ingen fetch.
   Håndtér: ikke-repo, intet remote, intet upstream, timeout → alt til `gray`/`red` som defineret.
2. **Backend-helper `dashboard_folders()`**: enumerer umiddelbare undermapper i
   `MASTERVERSIONER_ROOT` med skiplisten fra scope-reglen (+ de 4 foreslåede). Returnér mappenavn
   + sti. Genbrug mønsteret fra `/api/all-folders`.
3. **Endpoint `GET /api/repo-status`**: for hver mappe fra trin 2, kald trin 1 + `scan_project_urls`
   (til deploy-lampens "live-URL findes"). Læg root-repoet ind som første element. Læg en 60-sek.
   in-memory cache foran (samme `STATE_LOCK`-mønster). Bag `_is_external`-guarden (GET, kun localhost).
   *Verificér:* `curl localhost:7777/api/repo-status` returnerer JSON med ét element pr. mappe.
4. **Deploy-lampens data:** i trin 1, tilføj `git tag --points-at HEAD` + `git rev-list -n1 deployed`
   og kombinér med "live-URL findes" fra trin 3 til lampe 4's tilstand efter tabellen i afsnit 1.
5. **STATUS.md-lampen:** læs `<mappe>/STATUS.md`, find linjen `Senest opdateret:`, parse dato,
   sammenlign med i dag (30-dages-grænse). Findes ikke → rød; ingen læsbar dato → gul.
6. **Frontend — dashboard-view:** ny knap i Værktøjer-sektionen ("📊 Projekt-status" e.l.) der
   åbner et fuldskærms-view/modal (genbrug `openModal()`-mønsteret). Grid af kort som skitsen:
   projektnavn + 5 lamper i række med labels + en legend øverst. Ren CSS, ingen nye libs
   (Python stdlib + vanilla JS-reglen gælder også frontend).
7. **↻-knap + tomtilstande:** manuel genopfriskning (kalder `/api/repo-status` forbi cachen),
   og pæn visning når et kort er rent grønt vs. har alarmer. Sortér kort med alarmer øverst.
8. **Deploy-tag i `/luk`:** efter et vellykket production-deploy tilføjer `/luk`-skillen
   `git tag -f deployed HEAD`. Uden dette trin er deploy-lampen bare ærligt rød/grå — alt
   andet virker. Gør deploy-lampen ægte for ALLE deploy-mål (Cloudflare, github.io, politiken.dk).
9. **(Fase 2, valgfri) Cloudflare-verifikation:** ny helper der for de 6 `wrangler.toml`-projekter
   kalder Cloudflares deployments-API (token fra `.env`, samme urllib-mønster som `call_anthropic`),
   henter den live commit og sammenligner med HEAD. Vis "✓ Cloudflare bekræfter live" oven på
   tag-lampen for de projekter. Timeout → grå. Kræver at `/luk` deployer med
   `--commit-hash=$(git rev-parse HEAD)`.

**Modelnote:** Trin 1-8 er byggeri fra afgjort plan → **Sonnet**. Trin 9 (Cloudflare) er en
selvstændig senere opgave — kan vente til dashboardet har kørt et stykke tid.

---

## 5. Acceptkriterier (du tester selv i browseren)

Alle testes ved at åbne dashboardet og trykke ↻ efter hver handling:

1. **Ændringer→gul:** ret en fil i en testmappe (fx `echo x >> fil.txt`) uden at committe →
   mappens **Ændringer**-lampe bliver gul efter ↻. Commit → grøn igen.
2. **Pushet→gul:** commit uden at pushe → **Ændringer** grøn, **Pushet** gul. Push → grøn.
3. **Sikret→rød:** en mappe uden `.git` (fx `Hulemanden/`, `Dronningen/`) viser **Sikret** rød
   og lamperne 2-4 grå. Kør `git init` + tilføj remote → Sikret bliver grøn.
4. **Deployet:** et projekt med live-URL men uden `deployed`-tag viser **Deployet** rød; en mappe
   uden live-URL viser den grå. (Efter trin 8: kør `/luk`-deploy → grøn.)
5. **STATUS.md→rød/gul:** en mappe uden STATUS.md viser lampe 5 rød; en med gammel dato viser gul.
6. **Scope:** alle 66 mapper (minus skipliste) har et kort; root-repoet ligger øverst; ingen
   dubletter; `context/`, `fable/`, `_archive/`, `Backups/` er ikke med (hvis skiplisten bekræftes).
7. **Ydelse:** dashboardet loader inden for et par sekunder og gør IKKE resten af Command Center
   langsom (chat-listen poller stadig normalt imens).

---

## Første skridt for Sonnet-chatten

> Åbn en Sonnet-chat i `Chatoverblik/`. Start med **trin 1**: helper-funktionen
> `git_status_for(folder)` i chatoverblik.py, med de 6 verificerede git-kommandoer og de fire
> lampetilstande. Byg ét trin ad gangen, commit efter hvert, og stop og spørg hvis noget ikke
> er dækket af denne plan.
