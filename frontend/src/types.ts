export interface ChatSession {
  chat_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface TableCitation {
  type: 'table';
  tables: string[];
  sql: string;
  row_count: number;
  result_rows: Record<string, any>[];
}

export interface DocumentCitation {
  type: 'document';
  source?: string;
  file_name?: string;
  version?: string;
  date?: string;
  page?: number;
  section?: string;
  quote?: string;
  superseded?: Record<string, any>[];
}

export type Citation = TableCitation | DocumentCitation | Record<string, any>;

export interface ChatMessage {
  message_id: string;
  chat_id: string;
  role: 'user' | 'assistant';
  content: string;
  status?: string;
  interpreted_as?: string | null;
  web_enabled?: boolean;
  citations?: Citation[];
  metadata?: Record<string, any>;
  created_at?: string;
}

export interface ColumnProfile {
  name: string;
  data_type: string;
  null_count: number;
  null_pct: number;
  distinct_count: number;
  sample_values: any[];
}

export interface InferredRelationship {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  containment_ratio: number;
  confidence: number;
  status: string;
}

export interface TableProfile {
  table_name: string;
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  primary_key?: string | null;
  inferred_relationships: InferredRelationship[];
}

export interface DocumentMetadata {
  file_name: string;
  sha256: string;
  doc_title: string;
  version_family: string;
  doc_date?: string | null;
  doc_date_source: string;
  date_disagreement: boolean;
  page_count?: number | null;
  section_count: number;
  chunk_count: number;
}

export interface IngestionSummary {
  tables: TableProfile[];
  documents: DocumentMetadata[];
  version_families: Record<string, string[]>;
  documentation_loaded: boolean;
  errors: { file_name: string; error: string; reason: string }[];
  timestamp?: string;
}

export interface FileRecord {
  sha256: string;
  file_name: string;
  file_type: string;
  size_bytes: number;
  uploaded_at: string;
  doc_title: string;
  version_family: string;
  doc_date?: string | null;
  doc_date_source: string;
  page_count?: number | null;
  chunk_count: number;
}
