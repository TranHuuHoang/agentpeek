interface ViewTabsProps {
  active: string
  onChange: (tab: string) => void
}

const TABS: { id: string; icon: string; label: string }[] = [
  { id: 'topology', icon: '\u25C8', label: 'topology' },
  { id: 'timeline', icon: '\u2550', label: 'timeline' },
  { id: 'insights', icon: '\u25EA', label: 'insights' },
  { id: 'replay', icon: '\u25B6', label: 'replay' },
]

export default function ViewTabs({ active, onChange }: ViewTabsProps) {
  return (
    <div className="flex items-center gap-1 shrink-0">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-3 py-1 text-[11px] font-sans font-medium rounded-md transition-all ${
            active === tab.id
              ? 'bg-accent/15 text-accent'
              : 'text-[#A1A1AA] hover:text-[#D4D4D8] hover:bg-surface-elevated/50'
          }`}
        >
          <span className="mr-1">{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </div>
  )
}
