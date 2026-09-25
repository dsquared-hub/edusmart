/* Витрина дизайн-системы: токены, типографика и все компоненты во всех состояниях. */
import { BookOpen, Calculator, FlaskConical, Globe, Send, Star } from "lucide-react";
import { useState } from "react";
import { Kubi } from "@/components/avatar/Kubi";
import { Formula } from "@/components/Formula";
import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Button, Card, Coin, Icon3D, Modal, ProgressBar, Ring, SectionTitle, Segmented, Toggle } from "@/design-system/components";
import { useStore, type Mood } from "@/lib/store";

const SWATCHES = [
  ["bg", "#FAF6EF"],
  ["card", "#F3EAD9"],
  ["latte", "#D9C2A3"],
  ["caramel", "#B98A5E"],
  ["coffee", "#7A5236"],
  ["ink", "#3E2A1E"],
  ["gold", "#E8B64C"],
  ["good", "#6FA876"],
  ["bad", "#D2735A"],
] as const;

export default function DesignSystem() {
  const { d, skin } = useStore();
  const [modal, setModal] = useState(false);
  const [toggle, setToggle] = useState(true);
  const [seg, setSeg] = useState("a");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={d.design.title} subtitle={d.design.subtitle} />

      <Card>
        <SectionTitle>{d.design.colors}</SectionTitle>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-9">
          {SWATCHES.map(([name, hex]) => (
            <div key={name} className="flex flex-col gap-1.5">
              <div className="h-16 rounded-2xl border border-line" style={{ background: `rgb(var(--c-${name}))` }} />
              <div className="text-sm font-black">{name}</div>
              <div className="font-mono text-xs text-muted">{hex}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <SectionTitle>{d.design.type}</SectionTitle>
        <div className="flex flex-col gap-3">
          <div className="h-display">Display · Nunito 900</div>
          <div className="h-title">Title · Nunito 900</div>
          <div className="text-lg font-bold">Body large · Oʻquvchi · Ученик · Student</div>
          <div className="font-semibold text-muted">Body muted — вторичный текст, AA-контраст</div>
          <div className="label">Label · uppercase</div>
          <Formula big>S = (a + b) / 2 · h</Formula>
        </div>
      </Card>

      <Card>
        <SectionTitle>{d.design.buttons}</SectionTitle>
        <p className="mb-3 text-sm font-semibold text-muted">{d.design.states}</p>
        <div className="flex flex-wrap gap-3">
          <Button icon={<Send size={18} />}>Primary</Button>
          <Button variant="gold" icon={<Coin size={18} />}>Gold</Button>
          <Button variant="soft">Soft</Button>
          <Button variant="ghost">Ghost</Button>
          <Button disabled>{d.design.disabled}</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-4">
          <SectionTitle>{d.design.inputs}</SectionTitle>
          <input className="field" placeholder={d.ask.placeholder} />
          <input className="field" disabled value={d.design.disabled} readOnly />
          <Segmented label="demo" value={seg} onChange={setSeg} options={[{ value: "a", label: "Junior" }, { value: "b", label: "Senior" }]} />
          <Toggle label="Toggle" hint={d.profile.notifDaily} checked={toggle} onChange={setToggle} />
        </Card>

        <Card className="flex flex-col gap-4">
          <SectionTitle>{d.design.badges}</SectionTitle>
          <div className="flex flex-wrap gap-2">
            <Badge tone="gold"><Coin size={14} /> +25</Badge>
            <Badge tone="good">✓ {d.achievements.earned}</Badge>
            <Badge tone="bad">{d.teacher.needsHelp}</Badge>
            <Badge tone="coffee">Level 8</Badge>
            <Badge>{d.common.new}</Badge>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="chip" aria-pressed="true">{d.leaderboard.class}</button>
            <button className="chip">{d.leaderboard.school}</button>
            <button className="chip">{d.leaderboard.region}</button>
          </div>
          <SectionTitle>{d.design.progress}</SectionTitle>
          <ProgressBar value={72} />
          <ProgressBar value={45} tone="gold" size="lg" />
          <ProgressBar value={90} tone="good" size="sm" />
          <div className="flex gap-4">
            <Ring value={72} />
            <Ring value={30} size={64} />
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle>{d.design.icons}</SectionTitle>
        <div className="flex flex-wrap items-center gap-4">
          <Icon3D color="#B98A5E"><BookOpen size={28} /></Icon3D>
          <Icon3D color="#5E86B5"><Globe size={28} /></Icon3D>
          <Icon3D color="#6FA876"><FlaskConical size={28} /></Icon3D>
          <Icon3D color="#D98B4E"><Calculator size={28} /></Icon3D>
          <Icon3D color="#E8B64C"><Star size={28} /></Icon3D>
          <Coin size={48} />
          <Coin size={32} />
        </div>
      </Card>

      <Card>
        <SectionTitle>{d.design.avatar}</SectionTitle>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(["idle", "happy", "support", "thinking"] as Mood[]).map((m) => (
            <div key={m} className="flex flex-col items-center gap-2 rounded-2xl bg-card p-4">
              <Kubi stage={4} skin={skin} mood={m} size={110} />
              <span className="font-black text-coffee">{d.design.moods[m]}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <SectionTitle>{d.design.modal}</SectionTitle>
        <Button variant="soft" onClick={() => setModal(true)}>
          {d.design.openModal}
        </Button>
        <Modal open={modal} onClose={() => setModal(false)} title={d.design.modal}>
          <p className="mb-4 font-semibold text-muted">{d.design.modalText}</p>
          <Button className="w-full" onClick={() => setModal(false)}>
            {d.common.done}
          </Button>
        </Modal>
      </Card>
    </div>
  );
}
