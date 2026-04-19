data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ec2_s3_access" {
  name               = "${var.project_name}-ec2-s3-access"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

data "aws_iam_policy_document" "ec2_s3_read_repo_zip" {
  statement {
    effect = "Allow"
    actions = ["s3:GetObject"]
    resources = [
      "arn:aws:s3:::cpsc-559-repo-158210429599-us-west-2-an/DistributedInfraMonitoring.zip"
    ]
  }
}

resource "aws_iam_role_policy" "ec2_s3_read_repo_zip" {
  name   = "${var.project_name}-ec2-s3-read-repo-zip"
  role   = aws_iam_role.ec2_s3_access.id
  policy = data.aws_iam_policy_document.ec2_s3_read_repo_zip.json
}

resource "aws_iam_instance_profile" "ec2_s3_access" {
  name = "${var.project_name}-ec2-s3-access"
  role = aws_iam_role.ec2_s3_access.name
}