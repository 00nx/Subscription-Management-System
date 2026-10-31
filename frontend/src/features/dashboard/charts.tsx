import type { ReactNode } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { money } from '@/lib/format'

export const PALETTE = ['#4f46e5', '#16a34a', '#d97706', '#dc2626', '#0ea5e9', '#7c3aed', '#64748b']
const axis = { fontSize: 12, fill: '#64748b' }
const num = (v: string | number) => Number(v)

export function ChartCard({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-2"><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>
        {empty ? <p className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">No data for this period yet.</p> : <div className="h-[240px]" role="img" aria-label={title}>{children}</div>}
      </CardContent>
    </Card>
  )
}

const Frame = ({ children }: { children: React.ReactElement }) => <ResponsiveContainer width="100%" height="100%" minWidth={0}>{children}</ResponsiveContainer>
const shortPeriod = (p: string) => (p.length === 10 ? p.slice(5) : p)

export const AmountArea = ({ data }: { data: { period: string; amount: string }[] }) => (
  <Frame><AreaChart data={data.map((d) => ({ ...d, amount: num(d.amount) }))}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="period" tickFormatter={shortPeriod} tick={axis} /><YAxis tick={axis} width={60} />
    <Tooltip formatter={(v) => money(Number(v))} /><Area type="monotone" dataKey="amount" name="Collected" stroke={PALETTE[0]} fill={PALETTE[0]} fillOpacity={0.15} /></AreaChart></Frame>
)
export const AmountLine = ({ data, name }: { data: { period: string; amount: string }[]; name: string }) => (
  <Frame><LineChart data={data.map((d) => ({ ...d, amount: num(d.amount) }))}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="period" tickFormatter={(p) => p.slice(0, 7)} tick={axis} /><YAxis tick={axis} width={60} />
    <Tooltip formatter={(v) => money(Number(v))} /><Line type="monotone" dataKey="amount" name={name} stroke={PALETTE[1]} strokeWidth={2} dot={false} /></LineChart></Frame>
)
export const GrowthChart = ({ data }: { data: { period: string; new: number; total: number }[] }) => (
  <Frame><ComposedChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="period" tickFormatter={(p) => p.slice(0, 7)} tick={axis} /><YAxis tick={axis} width={40} allowDecimals={false} />
    <Tooltip /><Legend /><Bar dataKey="new" name="New" fill={PALETTE[0]} radius={[3, 3, 0, 0]} /><Line type="monotone" dataKey="total" name="Total" stroke={PALETTE[2]} strokeWidth={2} dot={false} /></ComposedChart></Frame>
)
export const Donut = ({ data, tooltip }: { data: { name: string; value: number; extra?: string }[]; tooltip?: (d: { name: string; value: number; extra?: string }) => string }) => (
  <Frame><PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>{data.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}</Pie>
    <Tooltip formatter={(v, n, item) => [tooltip ? tooltip(item.payload) : String(v), String(n)]} /><Legend /></PieChart></Frame>
)
export const OutstandingBars = ({ collected, outstanding }: { collected: string | null; outstanding: string }) => (
  <Frame><BarChart data={[{ name: 'Collected', amount: num(collected ?? 0) }, { name: 'Outstanding', amount: num(outstanding) }]}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="name" tick={axis} /><YAxis tick={axis} width={60} />
    <Tooltip formatter={(v) => money(Number(v))} /><Bar dataKey="amount" radius={[3, 3, 0, 0]}><Cell fill={PALETTE[1]} /><Cell fill={PALETTE[2]} /></Bar></BarChart></Frame>
)
