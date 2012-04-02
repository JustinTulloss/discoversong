-- Table: discoversong_user

-- DROP TABLE discoversong_user;

CREATE TABLE discoversong_user
(
  rdio_user_id integer,
  id serial NOT NULL,
  token text,
  secret text,
  address text,
  playlist text,
  CONSTRAINT pk PRIMARY KEY (id )
)
WITH (
  OIDS=FALSE
);
ALTER TABLE discoversong_user
  OWNER TO tguaspklkhnrpn;
