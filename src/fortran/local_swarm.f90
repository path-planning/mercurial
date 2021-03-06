!      program debug_mde
!      integer (kind=8) , parameter :: n = 5
!      real (kind=8) :: s_x = 10
!      real (kind=8) :: s_y = 10
!      real (kind=8) :: length = 1.5
!      real (kind=8), dimension(n,2) :: pos,swarm_force
!      integer, dimension(n) :: active
!      data pos / 1, 2.2, 3.4, 4.5, 6.7, 2.2, 2.5, 2, 7.4, 8.4/
!      active=1
!      call compute_mde(pos,s_x,s_y,active,length,n,swarm_force)
!      write(*,*) swarm_force
!      end

subroutine get_swarm_force(pos,velos,s_x,s_y,active,length,n,swarm_force)
! Adjust velocity to swarm by computing a correction force based on difference in velocities
! \da_i/dt = \sum_j w_ij*(v_j -v_i) ((check sign)) with w_ij 'gaussian' kernel based on distance

implicit none
integer (kind=8) ::  n
!f2py intent(in) pos,s_x,s_y,active,length
!f2py intent(out) swarm_force
!f2py depend(n) swarm_force
!
! this subroutine uses 1 based indexing
!
integer (kind=8) :: i,j,k,k2,l,max_val ! Looping variables
real (kind=8) :: s_x,s_y ! Domain size
real (kind=8), external :: weight_function

integer (kind=8) :: n_x,n_y ! binning stuff
integer (kind=8) :: nb_i,nb_j ! neighbour indices
real (kind=8):: length,dist,weight
integer (kind=8) :: num_in_radius ! number of neighbours in the radius

integer, dimension(n) :: active ! Whether pedestrian is active
real (kind=8), parameter :: eps = 0.0001
real (kind=8),dimension(n,2) :: pos,swarm_force,velos ! positions
integer (kind=8),dimension(n,2) :: cell_pos
real (kind=8) :: diff_x,diff_y

! Compute the distribution of particles
integer(kind=8),dimension(:,:),allocatable :: count_arr
integer(kind=8),dimension(:,:,:),allocatable :: bin_arr
n_x = int(s_x/length)+1
n_y = int(s_y/length)+1
allocate(count_arr(n_x,n_y))
count_arr=0
cell_pos = int(pos/length)+1
do k=1,n
    count_arr(cell_pos(k,1),cell_pos(k,2)) =&
    count_arr(cell_pos(k,1),cell_pos(k,2))+active(k)
end do
!write(*,*) count_arr

! Bin the particles
max_val = maxval(count_arr)
allocate(bin_arr(n_x,n_y,max_val))
bin_arr = 0
do k=1,n
    if (active(k)==1) then
        bin_arr(cell_pos(k,1),cell_pos(k,2),&
        count_arr(cell_pos(k,1),cell_pos(k,2))) = k ! Fill the bins backwards
        count_arr(cell_pos(k,1),cell_pos(k,2)) =&
        count_arr(cell_pos(k,1),cell_pos(k,2))-1
    end if
end do

! Compute the interactions (+80% of time)
swarm_force = 0
do k=1,n
    if (active(k)==1) then
        num_in_radius = 0
        do nb_i=-1,1
            i = nb_i + cell_pos(k,1)
            if (1<= i .and. i <=n_x) then
                do nb_j = -1,1
                    j = nb_j + cell_pos(k,2)
                    if (1<= j .and. j <=n_y) then
                        do l=1,max_val
                            k2 = bin_arr(i,j,l)
                            if (k2==0) then
                                exit
                            endif
                            if (k2/=k .and. active(k2)==1) then
                                diff_x = pos(k,1) - pos(k2,1)
                                diff_y = pos(k,2) - pos(k2,2)
                                dist = sqrt(diff_x*diff_x + diff_y*diff_y)
                                weight = weight_function(dist,length)
                                swarm_force(k,1) = swarm_force(k,1) +&
                                (velos(k2,1) - velos(k,1))*weight
                                swarm_force(k,2) = swarm_force(k,2) +&
                                (velos(k2,2) - velos(k,2))*weight ! Check sign
                                num_in_radius = num_in_radius + 1
                            end if
                        end do
                    end if
                end do
            end if
        end do
    end if
end do
return
end

real(kind=8) function weight_function(distance,length)
  ! Compute weight. Support of function is {distance < length}
  implicit none

  real (kind=8),parameter :: pi = 3.141592654
  real (kind=8) length ! smoothing distance
  real (kind=8) :: norm,weight,distance
  norm = 7.0/(pi*length*length)
  weight = max(1-distance/length,0.)**4*(1+distance/length)
  weight_function = norm*weight
end function
