export interface GraphViewNode {
  id: string;
  label: string;
  color?: string;
  size?: number;
  opacity?: number;
}

export interface GraphViewEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  color?: string;
  width?: number;
  dashed?: boolean;
  directed?: boolean;
  opacity?: number;
}

export interface GraphViewData {
  nodes: readonly GraphViewNode[];
  edges: readonly GraphViewEdge[];
  centerId?: string;
  selectedId?: string | null;
}

export interface GraphViewProps extends GraphViewData {
  onSelect?: (id: string | null) => void;
  onSelectEdge?: (id: string) => void;
  height?: number;
  className?: string;
  ariaLabel?: string;
}
