GRANT ALL PRIVILEGES ON DATABASE discordfarmdata TO discordfarm; 
GRANT ALL PRIVILEGES ON SCHEMA public to discordfarm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public to discordfarm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO discordfarm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO discordfarm;

CREATE TABLE IF NOT EXISTS public.profile(
    userid bigint PRIMARY KEY,
    xp bigint,
    money bigint,
    gems integer,
    tiles integer DEFAULT 2,
    factoryslots integer DEFAULT 1,
    factorylevel integer DEFAULT 0,
    storeslots integer DEFAULT 1,
    faction smallint,
    notifications boolean DEFAULT true,
    registration_date date DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS public.inventory(
    id SERIAL,
    userid bigint NOT NULL,
    itemid smallint NOT NULL,
    amount integer NOT NULL,
    PK_item_user PRIMARY KEY (userid, itemid)
);

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.planted(
    id SERIAL PRIMARY KEY,
    itemid smallint NOT NULL,
    userid bigint NOT NULL,
    amount integer NOT NULL,
    iterations smallint,
    fieldsused smallint DEFAULT 1, 
    ends timestamp NOT NULL,
    dies timestamp NOT NULL,
    robbedfields smallint DEFAULT 0,
    catboost boolean DEFAULT false
);

ALTER TABLE ONLY public.planted
    ADD CONSTRAINT planted_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.factory(
    id SERIAL PRIMARY KEY,
    userid bigint NOT NULL,
    itemid smallint NOT NULL,
    starts timestamp NOT NULL,
    ends timestamp NOT NULL
);

ALTER TABLE ONLY public.factory
    ADD CONSTRAINT factory_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;


CREATE TABLE IF NOT EXISTS public.missions(
    id SERIAL PRIMARY KEY,
    userid bigint NOT NULL, 
    requests text NOT NULL, 
    money integer NOT NULL, 
    xp integer NOT NULL,
    buisness text NOT NULL
);

ALTER TABLE ONLY public.missions
    ADD CONSTRAINT missions_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.store(
    id SERIAL PRIMARY KEY,
    guildid bigint NOT NULL,
    userid bigint NOT NULL,
    itemid smallint NOT NULL,
    amount integer NOT NULL,
    price integer NOT NULL,
    username text NOT NULL
);

ALTER TABLE ONLY public.store
    ADD CONSTRAINT store_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.boosts(
    userid bigint PRIMARY KEY,
    dog1 timestamp,
    dog2 timestamp,
    dog3 timestamp,
    cat timestamp,
    farm_slots timestamp,
    factory_slots timestamp
);

ALTER TABLE ONLY public.boosts
    ADD CONSTRAINT boosts_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;


CREATE TABLE IF NOT EXISTS public.modifications(
    id SERIAL,
    itemid bigint NOT NULL,
	userid bigint NOT NULL,
	time1 smallint DEFAULT 0,
	time2 smallint DEFAULT 0,
	volume smallint DEFAULT 0,
    CONSTRAINT PK_item_mod PRIMARY KEY (userid, itemid)
);

ALTER TABLE ONLY public.modifications
    ADD CONSTRAINT modifications_user_fkey FOREIGN KEY (userid) REFERENCES public.profile(userid) ON DELETE CASCADE;