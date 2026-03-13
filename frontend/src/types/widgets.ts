export type WidgetType =
  | 'CubeViewer'
  | 'DimensionTree'
  | 'DimensionEditor'
  | 'KPICard'
  | 'LineChart'
  | 'BarChart'
  | 'PieChart'
  | 'PivotTable'
  | 'DataGrid'
  | 'MDXEditor'
  | 'DimensionSetEditor'
  | 'PAWViewer'
  | 'PAWCubeViewer'
  | 'PAWDimensionEditor'
  | 'PAWBook'
  | 'SQLEditor'
  | 'DimensionControl'
  | 'TextBox'
  | 'Separator'

export interface WidgetConfig {
  id: string
  type: WidgetType
  title: string
  /** Grid position / size for canvas layout (grid-layout-plus) */
  x: number
  y: number
  w: number
  h: number
  props: Record<string, any>
  data?: any
  /** Currently displayed MDX (set by widget at runtime, not persisted) */
  mdx?: string
}

/** Height units per widget type (used when adding new widgets) */
export const DEFAULT_WIDGET_SIZES: Record<string, { w: number; h: number }> = {
  KPICard:             { w: 3, h: 4 },
  LineChart:           { w: 6, h: 8 },
  BarChart:            { w: 6, h: 8 },
  PieChart:            { w: 6, h: 8 },
  CubeViewer:          { w: 12, h: 16 },
  PivotTable:          { w: 9, h: 12 },
  DataGrid:            { w: 9, h: 10 },
  DimensionTree:       { w: 4, h: 8 },
  DimensionEditor:     { w: 6, h: 8 },
  DimensionSetEditor:  { w: 6, h: 12 },
  MDXEditor:           { w: 9, h: 12 },
  SQLEditor:           { w: 9, h: 12 },
  PAWViewer:           { w: 12, h: 30 },
  PAWCubeViewer:       { w: 9, h: 14 },
  PAWDimensionEditor:  { w: 9, h: 14 },
  PAWBook:             { w: 12, h: 14 },
  DimensionControl:    { w: 12, h: 3 },
  TextBox:             { w: 6, h: 4 },
  Separator:           { w: 12, h: 1 },
}

export interface OverviewPage {
  id: string
  name: string
  widgets: WidgetConfig[]
  is_default: boolean
}

/** Dimension control filter — broadcasted to all widgets on page */
export interface DimensionFilter {
  dimension: string
  member: string
  hierarchy?: string
}

export interface ToolCall {
  name: string
  input: Record<string, any>
  result: any
  id: string
  is_error?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  tool_calls?: ToolCall[]
  widgets?: WidgetConfig[]
  timestamp?: number
  has_errors?: boolean
  error_details?: string[]
}
