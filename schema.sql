-- PERMISSIONS

GRANT ALL PRIVILEGES ON DATABASE discordfarmdata TO discordfarm; 
GRANT ALL PRIVILEGES ON SCHEMA public to discordfarm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public to discordfarm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO discordfarm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO discordfarm;

-- TABLES

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
    payload text NOT NULL
);

ALTER TABLE ONLY public.missions
    ADD CONSTRAINT missions_user_fkey FOREIGN KEY (user_id) REFERENCES public.profile(user_id) ON DELETE CASCADE;

CREATE TABLE IF NOT EXISTS public.store(
    id SERIAL PRIMARY KEY,
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    username VARCHAR (64) NOT NULL,
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

CREATE TABLE IF NOT EXISTS public.guilds(
    guild_id bigint PRIMARY KEY,
    prefix VARCHAR (6) NOT NULL
);

-- FUNCTIONS

-- Profile statistics for the profile command
CREATE TYPE profile_stats AS (
    inventory_size integer, nearest_harvest timestamp, farm_slots_used integer,
    nearest_factory_production timestamp, store_slots_used integer
);

CREATE OR REPLACE FUNCTION get_profile_stats(user_id bigint, guild_id bigint) 
RETURNS profile_stats
AS
$$

DECLARE
    result_record profile_stats;

BEGIN
    SELECT sum(amount)
    INTO result_record.inventory_size
    FROM inventory
    WHERE inventory.user_id = $1
    AND item_id < 1000; -- exclude chests (id >= 1000)

    SELECT ends
    INTO result_record.nearest_harvest
    FROM farm
    WHERE farm.user_id = $1
    ORDER BY ends
    LIMIT 1;

    SELECT sum(fields_used)
    INTO result_record.farm_slots_used
    FROM farm
    WHERE farm.user_id = $1;

    SELECT ends
    INTO result_record.nearest_factory_production
    FROM factory
    WHERE factory.user_id = $1
    ORDER BY ends
    LIMIT 1;

    SELECT count(id)
    INTO result_record.store_slots_used
    FROM store
    WHERE store.user_id = $1
    AND store.guild_id = $2;

    RETURN result_record;

END
$$ LANGUAGE plpgsql;
