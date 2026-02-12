# approval_endpoints.py
"""
Regularization Approval/Rejection Endpoints with Authorization

These endpoints handle approval and rejection of both employee and admin regularization requests
with proper authorization checks based on approver_type field.

NOTE: Leave approval endpoints are in the main app file (app_py_for_leave_management_backend.py)
      Lines 1200-1290 contain leave approve/reject with authorization checks.

To integrate: Call register_regularization_approval_endpoints(app) after app initialization
"""

from flask import request, jsonify
from datetime import datetime
from database import SessionLocal, User, Regularization


def register_regularization_approval_endpoints(app):
    """Register regularization approval and rejection endpoints with authorization checks"""
    
    # =============================================================================
    # REGULARIZATION APPROVAL/REJECTION WITH AUTHORIZATION
    # =============================================================================
    
    @app.route('/api/regularization/<int:reg_id>/approve', methods=['PUT'])
    def approve_regularization(reg_id):
        """
        Approve regularization request with authorization check.
        - If approver_type = 'admin': Only admins can approve
        - If approver_type = 'manager': Only designated manager can approve
        """
        approver_id = request.headers.get('X-User-ID')
        
        if not approver_id:
            return jsonify({"message": "Approver ID required"}), 400
        
        db = SessionLocal()
        try:
            reg = db.query(Regularization).filter(Regularization.id == reg_id).first()
            
            if not reg:
                return jsonify({"message": "Regularization request not found"}), 404
            
            if reg.status != 'pending':
                return jsonify({"message": f"Request is already {reg.status}"}), 400
            
            # AUTHORIZATION CHECK
            if reg.approver_type == 'manager':
                if not reg.designated_approver_id:
                    return jsonify({"message": "No designated approver assigned"}), 400
                if int(approver_id) != reg.designated_approver_id:
                    return jsonify({"message": "Only the designated manager can approve"}), 403
            elif reg.approver_type == 'admin' or not reg.approver_type:
                # Employee requests - verify approver is admin
                approver = db.query(User).filter(User.id == int(approver_id)).first()
                if not approver or approver.role != 'admin':
                    return jsonify({"message": "Only admins can approve employee regularizations"}), 403
            else:
                return jsonify({"message": "Invalid approver type"}), 400
            
            # Approve
            reg.status = 'approved'
            reg.approved_by = int(approver_id)
            reg.approval_date = datetime.utcnow()
            
            db.commit()
            return jsonify({"message": "Regularization approved successfully"}), 200
            
        except Exception as e:
            db.rollback()
            print(f"Approve regularization error: {str(e)}")
            return jsonify({"message": f"Error: {str(e)}"}), 500
        finally:
            db.close()
    
    
    @app.route('/api/regularization/<int:reg_id>/reject', methods=['PUT'])
    def reject_regularization(reg_id):
        """
        Reject regularization request with authorization check.
        """
        data = request.get_json() or {}
        approver_id = request.headers.get('X-User-ID')
        
        if not approver_id:
            return jsonify({"message": "Approver ID required"}), 400
        
        db = SessionLocal()
        try:
            reg = db.query(Regularization).filter(Regularization.id == reg_id).first()
            
            if not reg:
                return jsonify({"message": "Regularization request not found"}), 404
            
            if reg.status != 'pending':
                return jsonify({"message": f"Request is already {reg.status}"}), 400
            
            # AUTHORIZATION CHECK (same as approve)
            if reg.approver_type == 'manager':
                if not reg.designated_approver_id:
                    return jsonify({"message": "No designated approver assigned"}), 400
                if int(approver_id) != reg.designated_approver_id:
                    return jsonify({"message": "Only the designated manager can reject"}), 403
            elif reg.approver_type == 'admin' or not reg.approver_type:
                approver = db.query(User).filter(User.id == int(approver_id)).first()
                if not approver or approver.role != 'admin':
                    return jsonify({"message": "Only admins can reject employee regularizations"}), 403
            else:
                return jsonify({"message": "Invalid approver type"}), 400
            
            # Reject
            reg.status = 'rejected'
            reg.rejection_reason = data.get('reason', 'Rejected')
            reg.approved_by = int(approver_id)
            
            db.commit()
            return jsonify({"message": "Regularization rejected"}), 200
            
        except Exception as e:
            db.rollback()
            print(f"Reject regularization error: {str(e)}")
            return jsonify({"message": f"Error: {str(e)}"}), 500
        finally:
            db.close()
    
    
    print("✓ Regularization approval/rejection endpoints registered with authorization checks")
