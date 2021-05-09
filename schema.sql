GRANT ALL PRIVILEGES ON DATABASE discordfarmdata TO discordfarm; 
GRANT ALL PRIVILEGES ON SCHEMA public to discordfarm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public to discordfarm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO discordfarm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO discordfarm;

CREATE TABLE IF NOT EXISTS public.profile(
    user_id bigint PRIMARY KEY,
    xp bigint DEFAULT 0,
    gold bigint DEFAULT 250,
    gems integer DEFAULT 0,
    farm_slots integer DEFAULT 2,
    factory_slots integer DEFAULT 1,
    factory_level integer DEFAULT 0,
    store_slots integer DEFAULT 1,
    notifications boolean DEFAULT true,
    registration_date date DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS public.inventory(
    id SERIAL,
    user_id bigint NOT NULL,
    item_id smallint NOT NULL,
    amount integer NOT NULL,
    CONSTRAINT PK_item_user PRIMARY KEY (user_id, item_id)
);

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.farm(
    id SERIAL PRIMARY KEY,
    item_id smallint NOT NULL,
    user_id bigint NOT NULL,
    amount integer NOT NULL,
    iterations smallint,
    fields_used smallint DEFAULT 1, 
    ends timestamp NOT NULL,
    dies timestamp NOT NULL,
    robbed_fields smallint DEFAULT 0,
    cat_boost boolean DEFAULT false
);

ALTER TABLE ONLY public.farm
    ADD CONSTRAINT farm_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.factory(
    id SERIAL PRIMARY KEY,
    user_id bigint NOT NULL,
    item_id smallint NOT NULL,
    starts timestamp NOT NULL,
    ends timestamp NOT NULL
);

ALTER TABLE ONLY public.factory
    ADD CONSTRAINT factory_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;


CREATE TABLE IF NOT EXISTS public.missions(
    id SERIAL PRIMARY KEY,
    user_id bigint NOT NULL, 
    requests text NOT NULL, 
    gold_reward integer NOT NULL, 
    xp_reward integer NOT NULL,
    buisness_name varchar(128) NOT NULL
);

ALTER TABLE ONLY public.missions
    ADD CONSTRAINT missions_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.store(
    id SERIAL PRIMARY KEY,
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    item_id smallint NOT NULL,
    amount integer NOT NULL,
    price integer NOT NULL
);

ALTER TABLE ONLY public.store
    ADD CONSTRAINT store_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.modifications(
    id SERIAL,
    item_id bigint NOT NULL,
    user_id bigint NOT NULL,
    time1 smallint DEFAULT 0,
    time2 smallint DEFAULT 0,
    volume smallint DEFAULT 0,
    CONSTRAINT PK_item_mod PRIMARY KEY (user_id, item_id)
);

ALTER TABLE ONLY public.modifications
    ADD CONSTRAINT modifications_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;