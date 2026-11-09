-- Project invitations and in-app notifications (docs/invite-system.md).
-- Mirrors the [Invitations] section of docs/database/schema.sql.

SET search_path = public, extensions;

CREATE TYPE invitation_status AS ENUM ('pending', 'accepted', 'declined', 'revoked', 'expired');

CREATE TABLE project_invitations (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id    BIGINT            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    email         CITEXT            NOT NULL,
    role          project_role      NOT NULL,
    status        invitation_status NOT NULL DEFAULT 'pending',
    invited_by    UUID              REFERENCES profiles(id) ON DELETE SET NULL,
    responded_by  UUID              REFERENCES profiles(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ       NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ       NOT NULL DEFAULT now() + interval '7 days',
    responded_at  TIMESTAMPTZ
);

-- One pending invitation per project + email.
CREATE UNIQUE INDEX uq_invitations_pending
    ON project_invitations (project_id, email) WHERE status = 'pending';
CREATE INDEX ix_invitations_email ON project_invitations (email) WHERE status = 'pending';

CREATE TABLE notifications (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       UUID         NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type          VARCHAR(40)  NOT NULL,
    project_id    BIGINT       REFERENCES projects(id) ON DELETE CASCADE,
    invitation_id BIGINT       REFERENCES project_invitations(id) ON DELETE CASCADE,
    actor_id      UUID         REFERENCES profiles(id) ON DELETE SET NULL,
    payload       JSONB,
    read_at       TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_notifications_user ON notifications (user_id, created_at DESC);
CREATE INDEX ix_notifications_unread ON notifications (user_id) WHERE read_at IS NULL;

-- When a profile is created or its email changes, deliver pending invitations for that email.
CREATE FUNCTION public.deliver_pending_invitations() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    INSERT INTO public.notifications (user_id, type, project_id, invitation_id, actor_id, payload)
    SELECT NEW.id, 'invitation', i.project_id, i.id, i.invited_by,
           jsonb_build_object(
               'project_name', p.name,
               'role', i.role,
               'actor_name', coalesce(nullif(a.full_name, ''), a.email::text, '')
           )
    FROM public.project_invitations i
    JOIN public.projects p ON p.id = i.project_id
    LEFT JOIN public.profiles a ON a.id = i.invited_by
    WHERE i.email = NEW.email
      AND i.status = 'pending'
      AND i.expires_at > now()
      AND p.archived_at IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM public.notifications n
          WHERE n.user_id = NEW.id AND n.invitation_id = i.id AND n.type = 'invitation'
      );
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_profile_created_deliver_invitations
    AFTER INSERT ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.deliver_pending_invitations();

CREATE TRIGGER on_profile_email_changed_deliver_invitations
    AFTER UPDATE OF email ON public.profiles
    FOR EACH ROW WHEN (OLD.email IS DISTINCT FROM NEW.email)
    EXECUTE FUNCTION public.deliver_pending_invitations();

-- RLS: enabled with no policies; only FastAPI (direct Postgres) reads app data.
ALTER TABLE project_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications       ENABLE ROW LEVEL SECURITY;
