# Command Center — installation til kolleger

Lokal webapp der scanner dine Claude- og Codex-chats og gør dem søgbare,
grupperer dem per projekt, og giver dig værktøjer (workflow-analyse,
genoptag-guide, ugens retro). Kører kun på din egen Mac. Cloud-AI er
default-deny: en API-key alene sender intet automatisk, og AI-knapper viser den
præcise payload før du aktivt bekræfter afsendelse.

---

## Inden du går i gang — tjekliste

Du har sandsynligvis allerede det meste. Hvis du er i tvivl, så åbn Terminal
og kør de små test-kommandoer.

- [ ] **macOS** (Command Center er kun bygget til Mac)
- [ ] **Python 3.9 eller nyere** — test: `python3 --version`
- [ ] **VS Code, Windsurf eller Cursor** — Command Center scanner alle tre hvis de er installeret
- [ ] **Claude Code-extension OG/ELLER Codex-extension** installeret i din editor — uden mindst én af dem er der ingen chats at vise
- [ ] **En Anthropic API-key** (valgfri — bruges kun når du aktivt bekræfter en AI-payload). Hent på <https://console.anthropic.com>. Uden den virker app'en, men AI-analyser og manuelle AI-resuméer kan ikke køres.

---

## Installation — 5 trin

### 1. Hent Command Center

Download fra GitHub:

**Uden git-kendskab** — gå til <https://github.com/kristianjensen5/Chatoverblik>,
klik den grønne **Code**-knap → **Download ZIP** → pak ud.

**Med git** — i Terminal:
```bash
git clone https://github.com/kristianjensen5/Chatoverblik.git
```

Læg den mappe **et sted hvor du har plads til projektmapper ved siden af**.
F.eks.:

```
~/Documents/CODE/MitVibeCoding/Chatoverblik/
```

Eller hvis du allerede har en mappe hvor dine eksperimenter ligger:

```
~/Documents/widgets/Chatoverblik/
```

> 💡 **Vigtigt:** Den mappe Chatoverblik ligger I, bliver behandlet som din
> "projekt-rod". Værktøjet kan kun se filer/projekter i den mappe og dens
> undermapper. Vælg derfor en placering hvor dine kode-projekter også ligger.

> 🔄 **Opdateringer:** Hvis du har klonet med `git`, hent nyeste version med
> `git pull` i Chatoverblik-mappen. Hvis du downloadede ZIP, hent en ny zip
> samme sted og udskift mappen.

### 2. Tilføj din Anthropic API-key (valgfri)

Åbn Terminal og kør:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
source ~/.zshrc
```

Indsæt din rigtige nøgle hvor der står `sk-ant-...`.

Nøglen aktiverer ikke automatisk sending af chats. Før en AI-knap sender noget,
viser Command Center payloaden i en tekstboks og kræver et aktivt klik på
**Send til cloud-AI**.

### 3. Start serveren første gang

Åbn Finder, gå til Chatoverblik-mappen og **dobbeltklik på `start.command`**.

Første gang siger macOS måske "kan ikke åbnes fordi den er fra en uidentificeret
udvikler". Højreklik på `start.command` → **Åbn** → bekræft. Derefter virker
dobbeltklik normalt.

Et Terminal-vindue popper op og viser:
```
Chatoverblik kører på  →  http://localhost:7777
```

### 4. Åbn UI'et

Gå til <http://localhost:7777> i Safari eller Chrome.

Første gang ser du "Scanner Claude-chats…" og "Henter AI-titler". Det tager
1-3 minutter første gang — derefter caches resultaterne, så fremtidige
opstarter er hurtige.

### 5. (Valgfri) Tilføj som Safari Web App

I Safari: **File → Add to Dock**. Du får en native-agtig app i Dock'en der
åbner UI'et med ét klik. Anbefales.

---

## Test at det virker

- [ ] Du ser dine chats grupperet under projekt-navne
- [ ] Klik en chat → modalen åbner med resumé + "Find chatten i VS Code"-knap
- [ ] Klik VS Code-knappen → editor åbner på projektmappen
- [ ] Klik "📊 Workflow-analyse" → AI genererer en analyse (kun hvis du har API-key)

---

## Almindelige problemer

**Kommer "Adresse er allerede i brug" når serveren starter**
Port 7777 er optaget af et andet program. Stop det andet program, eller spørg
Kristian om at gøre porten konfigurerbar.

**macOS spørger "Tillad indgående netværksforbindelser"**
Tryk **Tillad**. Hvis du afviste, gå til Systemindstillinger → Netværk →
Firewall og find Python på listen.

**Mobile preview virker ikke fra iPhone**
Tjek at iPhone og Mac er på samme WiFi (ikke Politikens corporate WiFi —
den blokerer klient-til-klient-trafik). Privat WiFi eller iPhone-hotspot
virker.

**Hvis du har en VPN aktiv** (f.eks. Politiken-VPN) — preview-URL'en kan
pege på VPN-IP'en som telefonen ikke kan nå. Sluk VPN, regenér QR-koden
(luk modal + klik 📱 Preview igen).

**Workspace Trust-banner vises i VS Code når Command Center åbner et projekt**
Klik "Yes, I trust the authors" én gang per projekt — så husker VS Code det.

---

## Hvad jeg (eller Kristian) gerne vil vide for at hjælpe dig

Hvis noget ikke virker, så svar på disse spørgsmål:

1. **Hvor har du pakket Chatoverblik ud?** (fuld sti, f.eks. `~/Documents/CODE/MitVibeCoding/Chatoverblik/`)
2. **Hvilke AI-extensions har du installeret?** Claude Code? Codex? Begge?
3. **Hvilken editor?** VS Code, Windsurf, Cursor — eller flere?
4. **Hvad står der i Terminal-vinduet** efter `start.command` er kørt? (kopier de første 10 linjer)
5. **Hvad står der i statuslinjen** i UI'et øverst (efter ikonet)?
6. **Hvis en specifik knap fejler:** hvilken? Og hvad sker der? (skærmbillede hjælper)
7. **Antal chats du forventer at se** — hvis du har brugt Claude Code/Codex i et par måneder skal du se 20-200 chats. Hvis du ser 0, så er der noget galt med scanning af `~/.claude/projects/` eller `~/.codex/sessions/`.

---

## Hvad app'en IKKE gør

- Sender intet til skyen undtagen til Anthropic (når AI-titler/analyser
  genereres — kun hvis du har API-key)
- Læser ikke andres chats — kun din egen bruger's
- Skriver ikke til chat-filer (kun cache.json i Chatoverblik-mappen, og
  HANDOVER.md hvis du klikker "📖 Genoptag-guide" på et projekt)
- Kører ikke autostartet — du skal selv starte den med `start.command`
