export interface TM1Element {
  name: string
  type: 'Numeric' | 'String' | 'Consolidated'
  level?: number
  weight?: number
  attributes?: Record<string, string | number>
}

export interface TM1Dimension {
  name: string
  elements?: TM1Element[]
  count?: number
}

export interface TM1Cube {
  name: string
  dimensions: string[]
  has_rules: boolean
}

export interface TM1HierarchyEdge {
  parent: string
  child: string
  weight: number
}

export interface MDXResult {
  headers: string[]
  rows: (string | number)[][]
  row_count: number
}

export interface TM1Attribute {
  name: string
  attribute_type: string
}
