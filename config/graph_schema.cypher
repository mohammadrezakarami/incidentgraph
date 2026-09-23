CREATE CONSTRAINT service_id_unique IF NOT EXISTS
FOR (node:Service) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT resource_id_unique IF NOT EXISTS
FOR (node:Resource) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT deployment_id_unique IF NOT EXISTS
FOR (node:Deployment) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT document_id_unique IF NOT EXISTS
FOR (node:Document) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS
FOR (node:Chunk) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
FOR (node:Incident) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT embedding_model_id_unique IF NOT EXISTS
FOR (node:EmbeddingModel) REQUIRE node.id IS UNIQUE;

CREATE CONSTRAINT corpus_id_unique IF NOT EXISTS
FOR (node:Corpus) REQUIRE node.id IS UNIQUE;

CREATE RANGE INDEX service_environment IF NOT EXISTS
FOR (node:Service) ON (node.environment);

CREATE RANGE INDEX document_validity IF NOT EXISTS
FOR (node:Document) ON (node.valid_from, node.valid_to);

CREATE RANGE INDEX chunk_document_id IF NOT EXISTS
FOR (node:Chunk) ON (node.document_id);

CREATE FULLTEXT INDEX chunk_text_fulltext IF NOT EXISTS
FOR (node:Chunk) ON EACH [node.text, node.section];

CREATE VECTOR INDEX chunk_embedding_vector IF NOT EXISTS
FOR (node:Chunk) ON node.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}};
