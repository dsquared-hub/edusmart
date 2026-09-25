import { Bell, LogOut, Monitor, Moon, Snowflake, Sun } from "lucide-react";
import { Kubi } from "@/components/avatar/Kubi";
import { LangSwitch, PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, Icon3D, Segmented, SectionTitle, Toggle } from "@/design-system/components";
import { navigate } from "@/lib/router";
import { fmt, useStore, type Mode, type ThemePref } from "@/lib/store";

export default function Profile() {
  const s = useStore();
  const { d } = s;
  const setNotif = (patch: Partial<typeof s.notif>) => s.set({ notif: { ...s.notif, ...patch } });

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={d.profile.title} />

      <Card className="mb-5 flex flex-col items-center gap-5 sm:flex-row">
        <Kubi stage={s.worn} skin={s.skin} mood={s.mood} size={120} />
        <div className="min-w-0 flex-1 text-center sm:text-left">
          <div className="text-2xl font-black text-coffee">{s.name}</div>
          <div className="font-semibold text-muted">
            {fmt(d.common.grade, { n: s.grade })} · {d.onboarding.roles[s.role].t}
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-2 sm:justify-start">
            <Badge tone="coffee">{fmt(d.common.level, { n: s.level })}</Badge>
            <Badge tone="gold">{d.wardrobe.stages[s.worn]}</Badge>
            {s.phone && <Badge>{s.phone}</Badge>}
          </div>
        </div>
      </Card>

      <div className="grid gap-5">
        <Card className="grid gap-5">
          <div className="flex flex-col gap-2">
            <span className="label">{d.common.lang}</span>
            <LangSwitch />
          </div>
          <div className="flex flex-col gap-2">
            <span className="label">{d.common.theme}</span>
            <Segmented<ThemePref>
              label={d.common.theme}
              value={s.theme}
              onChange={(theme) => s.set({ theme })}
              options={[
                { value: "light", label: <span className="inline-flex items-center gap-1.5"><Sun size={16} />{d.common.light}</span> },
                { value: "dark", label: <span className="inline-flex items-center gap-1.5"><Moon size={16} />{d.common.dark}</span> },
                { value: "system", label: <span className="inline-flex items-center gap-1.5"><Monitor size={16} />{d.common.system}</span> },
              ]}
            />
          </div>
          <div className="flex flex-col gap-2">
            <span className="label">{d.profile.mode}</span>
            <Segmented<Mode>
              label={d.profile.mode}
              value={s.mode}
              onChange={(mode) => s.set({ mode })}
              options={[
                { value: "junior", label: `🎈 ${d.common.junior}` },
                { value: "senior", label: `🎓 ${d.common.senior}` },
              ]}
            />
            <p className="text-sm font-semibold text-muted">{s.mode === "junior" ? d.profile.modeJunior : d.profile.modeSenior}</p>
          </div>
          <Toggle label={d.profile.reducedMotion} checked={s.reducedMotion} onChange={(reducedMotion) => s.set({ reducedMotion })} />
        </Card>

        <Card>
          <SectionTitle>
            <span className="inline-flex items-center gap-2">
              <Bell size={20} /> {d.profile.notifications}
            </span>
          </SectionTitle>
          <div className="divide-y divide-line">
            <Toggle label={d.profile.notifDaily} checked={s.notif.daily} onChange={(daily) => setNotif({ daily })} />
            {s.notif.daily && (
              <label className="flex items-center justify-between gap-4 py-3">
                <span className="font-bold">{d.profile.notifTime}</span>
                <input type="time" className="field !w-36" value={s.notif.time} onChange={(e) => setNotif({ time: e.target.value })} />
              </label>
            )}
            <Toggle label={d.profile.notifQuiet} checked={s.notif.quiet} onChange={(quiet) => setNotif({ quiet })} />
            <Toggle label={d.profile.notifReports} checked={s.notif.reports} onChange={(reports) => setNotif({ reports })} />
            <Toggle label={d.profile.weekend} checked={s.notif.weekend} onChange={(weekend) => setNotif({ weekend })} />
          </div>
        </Card>

        <Card cream className="flex items-center gap-4">
          <Icon3D color="#5E9ACB" size={52}>
            <Snowflake size={26} />
          </Icon3D>
          <div>
            <div className="font-black text-coffee">{d.profile.freeze}</div>
            <div className="text-sm font-semibold text-muted">{fmt(d.profile.freezeText, { n: s.freezes })}</div>
          </div>
        </Card>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Button variant="soft" className="flex-1" onClick={() => { s.set({ onboarded: false }); navigate("/onboarding"); }}>
            {d.profile.replayOnboarding}
          </Button>
          <Button variant="ghost" className="flex-1" icon={<LogOut size={18} />} onClick={() => { s.reset(); navigate("/onboarding"); }}>
            {d.profile.logout}
          </Button>
        </div>
      </div>
    </div>
  );
}
