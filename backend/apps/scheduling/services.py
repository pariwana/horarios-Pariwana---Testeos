from apps.audit.services import AuditService
from apps.scheduling.models import ScheduleAssignment


class ScheduleAssignmentService:
    @staticmethod
    def upsert_assignment(*, tenant, property_obj, worker, date, shift=None, special_state=None, user=None):
        assignment, created = ScheduleAssignment.objects.get_or_create(
            tenant=tenant,
            property=property_obj,
            worker=worker,
            date=date,
        )
        before = {
            "shift_id": assignment.shift_id,
            "special_state_id": assignment.special_state_id,
        }
        assignment.shift = shift
        assignment.special_state = special_state
        assignment.updated_by = user
        if created:
            assignment.created_by = user
        assignment.full_clean()
        assignment.save()
        if user is not None:
            AuditService.log(
                tenant=tenant,
                property_obj=property_obj,
                user=user,
                action="schedule_assignment_upsert",
                entity_type="ScheduleAssignment",
                entity_id=assignment.id,
                before=before,
                after={"shift_id": assignment.shift_id, "special_state_id": assignment.special_state_id},
            )
        return assignment
